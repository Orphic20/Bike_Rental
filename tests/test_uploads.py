import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost:5432/test",
)

from bike_rental.routers import uploads


def test_cloudinary_public_id_accepts_only_expected_folder():
    bike_url = (
        "https://res.cloudinary.com/demo/image/upload/"
        "v1720000000/munoz/bikes/bike-photo.webp"
    )
    receipt_url = (
        "https://res.cloudinary.com/demo/image/upload/"
        "v1720000000/munoz/receipts/old-slip.webp"
    )
    assert (
        uploads.cloudinary_public_id(bike_url, folder="munoz/bikes")
        == "munoz/bikes/bike-photo"
    )
    assert (
        uploads.cloudinary_public_id(receipt_url, folder="munoz/receipts")
        == "munoz/receipts/old-slip"
    )
    assert uploads.cloudinary_public_id(bike_url, folder="munoz/receipts") is None
    assert uploads.cloudinary_public_id(receipt_url, folder="munoz/bikes") is None
    assert (
        uploads.cloudinary_public_id(
            "https://example.com/munoz/bikes/bike-photo.webp",
            folder="munoz/bikes",
        )
        is None
    )


def test_delete_cloudinary_image_uses_extracted_public_id(monkeypatch):
    calls = []
    monkeypatch.setattr(uploads, "_configure_cloudinary", lambda: None)
    monkeypatch.setattr(
        uploads.cloudinary.uploader,
        "destroy",
        lambda public_id, **options: calls.append((public_id, options))
        or {"result": "ok"},
    )

    deleted = uploads.delete_cloudinary_image(
        "https://res.cloudinary.com/demo/image/upload/"
        "v1720000000/munoz/bikes/old-bike.jpg",
        folder="munoz/bikes",
    )

    assert deleted is True
    assert calls == [
        (
            "munoz/bikes/old-bike",
            {"resource_type": "image", "invalidate": True},
        )
    ]
