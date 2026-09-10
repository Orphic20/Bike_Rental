"""Customer receipt uploads (Cloudinary)."""

import os

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, HTTPException, UploadFile

from bike_rental.auth import CurrentUser

router = APIRouter(prefix="/uploads", tags=["uploads"])


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


@router.post("/receipt")
def upload_receipt(
    file: UploadFile,
    _user: CurrentUser,
) -> dict[str, str]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Receipt must be an image")

    _configure_cloudinary()
    result = cloudinary.uploader.upload(
        file.file,
        folder="munoz/receipts",
        resource_type="image",
    )
    return {"url": result["secure_url"]}
