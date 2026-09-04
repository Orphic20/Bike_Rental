"""Creating and viewing bookings, including the rentals inside them."""

from fastapi import APIRouter

router = APIRouter(prefix="/bookings", tags=["bookings"])
