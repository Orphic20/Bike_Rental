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
    GcashVerify,
    PaymentMethod,
    PaymentStatus,
    Rental,
    RentalRead,
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
                gcash_ref_no=booking.gcash_ref_no,
                gcash_receipt_url=booking.gcash_receipt_url,
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


@router.post("/rentals/{rental_id}/return", response_model=RentalRead)
def return_rental(
    rental_id: uuid.UUID,
    user: StaffUser,
    session: SessionDep,
) -> RentalRead:
    rental = session.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    if rental.status not in (RentalStatus.active, RentalStatus.overdue):
        raise HTTPException(status_code=400, detail="Rental is not outstanding")

    bike = session.get(Bike, rental.bike_id)
    if bike is None:
        raise HTTPException(status_code=500, detail="Rental has no bike")
    if bike.status != BikeStatus.rented:
        raise HTTPException(status_code=400, detail="Bike is not rented")

    now = datetime.now(timezone.utc)
    rental.returned_at = now
    rental.status = RentalStatus.returned
    bike.status = BikeStatus.available

    session.add(rental)
    session.commit()
    session.refresh(rental)
    return RentalRead(
        id=rental.id,
        bike_id=rental.bike_id,
        bike_name=bike.name,
        bike_type=bike.type,
        released_at=rental.released_at,
        due_at=rental.due_at,
        returned_at=rental.returned_at,
        price=rental.price,
        status=rental.status,
    )


@router.get("/payments/pending", response_model=list[StaffBookingRead])
def list_pending_gcash(
    user: StaffUser,
    session: SessionDep,
) -> list[StaffBookingRead]:
    pairs = session.exec(
        select(Booking, User)
        .join(User, User.id == Booking.user_id)
        .where(Booking.payment_method == PaymentMethod.gcash)
        .where(Booking.payment_status == PaymentStatus.pending_verification)
        .order_by(Booking.created_at.desc())
    ).all()
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
                gcash_ref_no=booking.gcash_ref_no,
                gcash_receipt_url=booking.gcash_receipt_url,
            )
        )
    return result


@router.post("/payments/{booking_id}/verify", response_model=BookingRead)
def verify_gcash_payment(
    booking_id: uuid.UUID,
    body: GcashVerify,
    user: StaffUser,
    session: SessionDep,
) -> BookingRead:
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.payment_method != PaymentMethod.gcash:
        raise HTTPException(status_code=400, detail="Payment method is not gcash")
    if booking.payment_status != PaymentStatus.pending_verification:
        raise HTTPException(status_code=400, detail="Payment status is not pending verification")
    if booking.amount_paid != 0:
        raise HTTPException(status_code=400, detail="Amount paid is not 0")

    if body.decision == "accepted":
        booking.amount_paid = booking.total_price
        booking.payment_status = PaymentStatus.paid
    else:
        booking.payment_status = PaymentStatus.rejected

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