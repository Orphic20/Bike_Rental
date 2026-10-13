"""Image uploads (Cloudinary): receipts and bike photos."""

import logging
import os
import re
from urllib.parse import unquote, urlparse

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from bike_rental.auth import AdminUser, CurrentUser
from bike_rental.rate_limit import limit_uploads

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)


def _configure_cloudinary() -> None:
    if cloudinary.config().cloud_name:
        return
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    if not cloudinary.config().cloud_name:
        raise HTTPException(status_code=500, detail="Image uploads are not configured")


def _upload_image(file: UploadFile, *, folder: str, label: str) -> dict[str, str]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"{label} must be an image")
    _configure_cloudinary()
    result = cloudinary.uploader.upload(
        file.file,
        folder=folder,
        resource_type="image",
    )
    return {"url": result["secure_url"]}


def cloudinary_public_id(image_url: str | None, *, folder: str) -> str | None:
    """Extract a public ID only from Cloudinary assets inside the expected folder."""
    if not image_url:
        return None
    parsed = urlparse(image_url)
    if parsed.scheme != "https" or parsed.hostname != "res.cloudinary.com":
        return None

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    try:
        upload_index = parts.index("upload")
    except ValueError:
        return None

    asset_parts = parts[upload_index + 1 :]
    if asset_parts and re.fullmatch(r"v\d+", asset_parts[0]):
        asset_parts = asset_parts[1:]
    if len(asset_parts) < 2:
        return None

    public_id = "/".join(asset_parts).rsplit(".", 1)[0]
    if not public_id.startswith(f"{folder}/"):
        return None
    return public_id


def delete_cloudinary_image(image_url: str | None, *, folder: str) -> bool:
    """Best-effort cleanup after the database no longer references an image."""
    public_id = cloudinary_public_id(image_url, folder=folder)
    if public_id is None:
        return False
    try:
        _configure_cloudinary()
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
            invalidate=True,
        )
    except Exception:
        logger.exception("Could not delete replaced Cloudinary image %s", public_id)
        return False
    return result.get("result") in {"ok", "not found"}


@router.post("/receipt")
def upload_receipt(
    file: UploadFile,
    _user: CurrentUser,
    _: None = Depends(limit_uploads),
) -> dict[str, str]:
    return _upload_image(file, folder="munoz/receipts", label="Receipt")


@router.post("/bike")
def upload_bike_photo(
    file: UploadFile,
    _user: AdminUser,
) -> dict[str, str]:
    return _upload_image(file, folder="munoz/bikes", label="Bike photo")
