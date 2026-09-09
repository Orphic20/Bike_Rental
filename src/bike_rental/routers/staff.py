"""Counter workflow: search, release, return, bike status changes."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter
from sqlmodel import or_, select

from bike_rental.auth import StaffUser
from bike_rental.database import SessionDep
from bike_rental.models import Bike, Booking, Rental, RentalStatus, StaffBookingRead, User
from bike_rental.routers.bookings import _to_read

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/bookings", response_model=list[StaffBookingRead])
def list_staff_bookings(
    user: StaffUser,
    session: SessionDep,
    q: str | None = None,
    tab: Literal["today", "outstanding"] | None = None,
) -> list[StaffBookingRead]:
    stmt = (
        select(Booking, User)
        .join(User, User.id == Booking.user_id)
        .order_by(Booking.created_at.desc())
    )
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Booking.booking_ref.ilike(term),
                User.name.ilike(term),
                User.email.ilike(term),
            )
        )
    if tab == "today":
        stmt = stmt.where(Booking.expected_pickup_date == date.today())
    elif tab == "outstanding":
        stmt = stmt.where(
            Booking.id.in_(
                select(Rental.booking_id).where(
                    Rental.status.in_(
                        (RentalStatus.active, RentalStatus.overdue)
                    )
                )
            )
        )
    pairs = session.exec(stmt).all()
    if not pairs:
        return []
    rows = session.exec(
        select(Rental, Bike)
        .join(Bike, Bike.id == Rental.bike_id)
        .where(Rental.booking_id.in_([booking.id for booking, _ in pairs]))
        .order_by(Rental.id)
        ).all()

    grouped: dict[uuid.UUID, list[tuple[Rental, Bike]]] = {}
    for rental, bike in rows:
        grouped.setdefault(rental.booking_id, []).append((rental, bike))
    result = []
    for booking, customer in pairs:
        base = _to_read(booking, grouped.get(booking.id, []))
        result.append(
            StaffBookingRead(
                **base.model_dump(),
                customer_name=customer.name,
                customer_email=customer.email,
        )
        )
    return result
