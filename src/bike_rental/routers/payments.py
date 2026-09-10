"""GCash receipt verification and cash-on-pickup settlement."""

from fastapi import APIRouter
import uuid
from fastapi import HTTPException
from bike_rental.auth import StaffUser
from bike_rental.database import SessionDep
from bike_rental.models import Bike, Booking, BookingRead, PaymentMethod, PaymentStatus, Rental
from sqlmodel import select
from bike_rental.routers.bookings import _to_read

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/{booking_id}/cash", response_model=BookingRead)
def cash_on_pickup(
    booking_id: uuid.UUID,
    user: StaffUser,
    session: SessionDep,
) -> BookingRead:
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.payment_method != PaymentMethod.cash:
        raise HTTPException(status_code=400, detail="Payment method is not cash")
    if booking.payment_status != PaymentStatus.unpaid_pending_pickup:
        raise HTTPException(status_code=400, detail="Payment status is not pending")
    if booking.amount_paid != 0:
        raise HTTPException(status_code=400, detail="Amount paid is not 0")
    booking.amount_paid = booking.total_price
    booking.payment_status = PaymentStatus.paid
    session.add(booking)
    session.commit()
    session.refresh(booking)
    rentals = session.exec(
        select(Rental, Bike)
        .join(Bike, Bike.id == Rental.bike_id)
        .where(Rental.booking_id == booking.id)
        .order_by(Rental.id)
    ).all()
    return _to_read(booking, list(rentals))
 
    