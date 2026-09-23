"""Image uploads (Cloudinary): receipts and bike photos."""

import os

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from bike_rental.auth import AdminUser, CurrentUser
from bike_rental.rate_limit import limit_uploads

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
