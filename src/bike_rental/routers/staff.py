"""Counter workflow: search, release, return, bike status changes."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from sqlmodel import or_, select

from bike_rental.auth import StaffUser
from bike_rental.availability import span_days
from bike_rental.database import SessionDep
from bike_rental.models import (
    Bike,
    BikeStatus,
    Booking,
    BookingRead,
    Rental,
    RentalStatus,
    StaffBookingRead,
    User,
)
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


@router.post("/bookings/{booking_id}/release", response_model=BookingRead)
def release_booking(
    booking_id: uuid.UUID,
    user: StaffUser,
    session: SessionDep,
) -> BookingRead:
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.amount_paid != booking.total_price:
        raise HTTPException(status_code=400, detail="Booking is not fully paid")

    rows = session.exec(
        select(Rental, Bike)
        .join(Bike, Bike.id == Rental.bike_id)
        .where(Rental.booking_id == booking.id)
        .order_by(Rental.id)
    ).all()
    if not rows:
        raise HTTPException(status_code=400, detail="Booking has no rentals")

    now = datetime.now(timezone.utc)
    last_day = now.date() + timedelta(days=span_days(booking.rate_selected) - 1)
    due_at = datetime(
        last_day.year,
        last_day.month,
        last_day.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )

    for rental, bike in rows:
        if rental.status != RentalStatus.reserved:
            raise HTTPException(
                status_code=400,
                detail="Booking has already been released",
            )
        rental.released_at = now
        rental.due_at = due_at
        rental.status = RentalStatus.active
        bike.status = BikeStatus.rented

    session.commit()
    session.refresh(booking)
    for rental, _ in rows:
        session.refresh(rental)
    return _to_read(booking, list(rows))