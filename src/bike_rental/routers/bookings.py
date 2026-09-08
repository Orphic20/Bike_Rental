"""Creating and viewing bookings, including the rentals inside them."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from bike_rental.auth import CurrentUser
from bike_rental.availability import (
    BLOCKING_STATUSES,
    existing_window,
    window,
    windows_overlap,
)
from bike_rental.database import SessionDep
from bike_rental.models import (
    Bike,
    BikeStatus,
    Booking,
    BookingCreate,
    BookingRead,
    BookingType,
    PaymentMethod,
    PaymentStatus,
    RateSelected,
    Rental,
    RentalRead,
    RentalStatus,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _to_read(booking: Booking, rentals: list[tuple[Rental, Bike | None]]) -> BookingRead:
    return BookingRead(
        id=booking.id,
        booking_ref=booking.booking_ref,
        expected_pickup_date=booking.expected_pickup_date,
        rate_selected=booking.rate_selected,
        total_price=booking.total_price,
        amount_paid=booking.amount_paid,
        balance_due=booking.balance_due,
        payment_method=booking.payment_method,
        payment_status=booking.payment_status,
        booking_type=booking.booking_type,
        created_at=booking.created_at,
        rentals=[
            RentalRead(
                id=rental.id,
                bike_id=rental.bike_id,
                bike_name=bike.name if bike else None,
                bike_type=bike.type if bike else None,
                released_at=rental.released_at,
                due_at=rental.due_at,
                returned_at=rental.returned_at,
                price=rental.price,
                status=rental.status,
            )
            for rental, bike in rentals
        ],
    )


@router.post("", response_model=BookingRead)
def create_booking(
    body: BookingCreate,
    user: CurrentUser,
    session: SessionDep,
) -> BookingRead:
    bike_ids = [item.bike_id for item in body.bikes]
    if not bike_ids:
        raise HTTPException(status_code=400, detail="At least one bike is required")
    if len(bike_ids) != len(set(bike_ids)):
        raise HTTPException(status_code=400, detail="Duplicate bikes in request")

    if body.payment_method == PaymentMethod.gcash:
        if not body.gcash_ref_no or not body.gcash_receipt_url:
            raise HTTPException(
                status_code=400,
                detail="GCash requires a reference number and receipt URL",
            )
        payment_status = PaymentStatus.pending_verification
    else:
        if body.gcash_ref_no or body.gcash_receipt_url:
            raise HTTPException(
                status_code=400,
                detail="Cash bookings cannot include GCash fields",
            )
        payment_status = PaymentStatus.unpaid_pending_pickup

    bikes = session.exec(
        select(Bike)
        .where(Bike.id.in_(bike_ids))
        .order_by(Bike.id)
        .with_for_update()
    ).all()
    by_id = {bike.id: bike for bike in bikes}
    if len(by_id) != len(bike_ids):
        raise HTTPException(status_code=404, detail="One or more bikes were not found")

    new_start, new_end = window(body.expected_pickup_date, body.rate_selected)
    total = Decimal("0")
    prices: list[Decimal] = []

    for bike_id in bike_ids:
        bike = by_id[bike_id]
        if bike.status in (BikeStatus.maintenance, BikeStatus.retired):
            raise HTTPException(
                status_code=409,
                detail=f"Bike {bike.name} is not bookable",
            )
        if body.rate_selected == RateSelected.weekly:
            if bike.weekly_rate is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Bike {bike.name} has no weekly rate",
                )
            price = bike.weekly_rate
        else:
            price = bike.daily_rate
        prices.append(price)
        total += price

        existing = session.exec(
            select(Rental, Booking)
            .join(Booking, Booking.id == Rental.booking_id)
            .where(Rental.bike_id == bike.id)
            .where(Rental.status.in_(BLOCKING_STATUSES))
        ).all()
        for rental, parent in existing:
            exist_start, exist_end = existing_window(rental, parent)
            if windows_overlap(new_start, new_end, exist_start, exist_end):
                raise HTTPException(
                    status_code=409,
                    detail=f"Bike {bike.name} is not available on that date",
                )

    row = Booking(
        user_id=user.id,
        total_price=total,
        amount_paid=Decimal("0"),
        payment_method=body.payment_method,
        payment_status=payment_status,
        gcash_ref_no=body.gcash_ref_no,
        gcash_receipt_url=body.gcash_receipt_url,
        expected_pickup_date=body.expected_pickup_date,
        rate_selected=body.rate_selected,
        booking_type=BookingType.new,
        waiver_version=body.waiver_version,
        waiver_accepted_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()

    rentals: list[Rental] = []
    for bike_id, price in zip(bike_ids, prices, strict=True):
        rental = Rental(
            booking_id=row.id,
            bike_id=bike_id,
            price=price,
            status=RentalStatus.reserved,
        )
        session.add(rental)
        rentals.append(rental)

    session.commit()
    session.refresh(row)
    for rental in rentals:
        session.refresh(rental)

    return _to_read(row, [(rental, by_id[rental.bike_id]) for rental in rentals])


@router.get("", response_model=list[BookingRead])
def list_my_bookings(
    user: CurrentUser,
    session: SessionDep,
) -> list[BookingRead]:
    """Every booking the caller owns, newest first — this is "My rides"."""
    bookings = session.exec(
        select(Booking)
        .where(Booking.user_id == user.id)
        .order_by(Booking.created_at.desc())
    ).all()
    if not bookings:
        return []

    rows = session.exec(
        select(Rental, Bike)
        .join(Bike, Bike.id == Rental.bike_id)
        .where(Rental.booking_id.in_([booking.id for booking in bookings]))
        .order_by(Rental.id)
    ).all()

    grouped: dict[uuid.UUID, list[tuple[Rental, Bike]]] = {}
    for rental, bike in rows:
        grouped.setdefault(rental.booking_id, []).append((rental, bike))

    return [_to_read(booking, grouped.get(booking.id, [])) for booking in bookings]


@router.get("/{booking_id}", response_model=BookingRead)
def read_booking(
    booking_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> BookingRead:
    booking = session.get(Booking, booking_id)
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    rentals = session.exec(
        select(Rental, Bike)
        .join(Bike, Bike.id == Rental.bike_id)
        .where(Rental.booking_id == booking.id)
        .order_by(Rental.id)
    ).all()
    return _to_read(booking, list(rentals))
