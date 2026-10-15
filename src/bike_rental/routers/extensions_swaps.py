"""Customer extension/swap requests and the corresponding staff decisions."""

import uuid
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import DataError, IntegrityError
from sqlmodel import select

from bike_rental.auth import CurrentUser, StaffUser
from bike_rental.availability import (
    BLOCKING_STATUSES,
    ensure_aware,
    existing_window,
    overlapping_full_day_closure,
    span_days,
    windows_overlap,
)
from bike_rental.database import SessionDep
from bike_rental.lifecycle import SHOP_CLOSING_TIME, SHOP_TIME_ZONE
from bike_rental.models import (
    AuditLog,
    Bike,
    BikeStatus,
    Booking,
    BookingRead,
    BookingType,
    ExtensionCreate,
    PaymentMethod,
    PaymentStatus,
    RateSelected,
    Rental,
    RentalStatus,
    SwapDecision,
    SwapRequest,
    SwapRequestCreate,
    SwapRequestRead,
    SwapStatus,
    User,
)
from bike_rental.routers.bookings import _to_read

router = APIRouter(tags=["extensions & swaps"])


def _extension_dates(rental: Rental, rate) -> tuple:
    if rental.due_at is None:
        raise HTTPException(status_code=400, detail="Rental has no due time")
    start = ensure_aware(rental.due_at).astimezone(SHOP_TIME_ZONE).date() + timedelta(days=1)
    end = start + timedelta(days=span_days(rate))
    return start, end


def _extension_due_at(start, rate) -> datetime:
    final_date = start + timedelta(days=span_days(rate) - 1)
    return datetime.combine(
        final_date, SHOP_CLOSING_TIME, tzinfo=SHOP_TIME_ZONE
    ).astimezone(timezone.utc)


def _bike_has_conflict(
    session,
    *,
    bike_id: uuid.UUID,
    start,
    end,
    exclude_rental_id: uuid.UUID | None = None,
) -> bool:
    rows = session.exec(
        select(Rental, Booking)
        .join(Booking, Booking.id == Rental.booking_id)
        .where(Rental.bike_id == bike_id)
        .where(Rental.status.in_(BLOCKING_STATUSES))
    ).all()
    return any(
        rental.id != exclude_rental_id
        and windows_overlap(start, end, *existing_window(rental, booking))
        for rental, booking in rows
    )


def _extension_insert_error(exc: Exception) -> str:
    message = str(getattr(exc, "orig", exc)).lower()
    if "one_pending_extension" in message:
        return "This rental already has an extension awaiting payment or approval"
    if "booking_type" in message:
        return "Extension bookings are not enabled on the database yet"
    if "waiver" in message:
        return "The original booking is missing a waiver"
    return "Could not create this extension"


def _payment_state(body: ExtensionCreate) -> PaymentStatus:
    if body.payment_method == PaymentMethod.gcash:
        if not (body.gcash_ref_no or "").strip() or not (
            body.gcash_receipt_url or ""
        ).strip():
            raise HTTPException(
                status_code=400,
                detail="GCash requires a reference number and receipt URL",
            )
        return PaymentStatus.pending_verification
    if body.gcash_ref_no or body.gcash_receipt_url:
        raise HTTPException(
            status_code=400,
            detail="Cash extensions cannot include GCash fields",
        )
    return PaymentStatus.unpaid_pending_pickup


@router.post("/rentals/{rental_id}/extensions", response_model=BookingRead)
def create_extension(
    rental_id: uuid.UUID,
    body: ExtensionCreate,
    user: CurrentUser,
    session: SessionDep,
) -> BookingRead:
    pair = session.exec(
        select(Rental, Booking)
        .join(Booking, Booking.id == Rental.booking_id)
        .where(Rental.id == rental_id)
        .with_for_update()
    ).first()
    if pair is None or pair[1].user_id != user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    rental, original = pair
    if rental.status != RentalStatus.active:
        raise HTTPException(status_code=400, detail="Only active rentals can be extended")
    if rental.due_at is None or ensure_aware(rental.due_at) <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Past-due rentals cannot be extended",
        )

    pending = session.exec(
        select(Booking)
        .where(Booking.booking_type == BookingType.extension)
        .where(Booking.rental_id == rental.id)
        .where(Booking.extension_applied_at.is_(None))
        .where(
            Booking.payment_status.notin_(
                (PaymentStatus.cancelled, PaymentStatus.rejected)
            )
        )
    ).first()
    if pending is not None:
        raise HTTPException(
            status_code=409,
            detail="This rental already has an extension awaiting payment or approval",
        )

    bike = session.exec(
        select(Bike).where(Bike.id == rental.bike_id).with_for_update()
    ).first()
    if bike is None:
        raise HTTPException(status_code=500, detail="Rental has no bike")
    if body.rate_selected == RateSelected.weekly:
        if bike.weekly_rate is None:
            raise HTTPException(status_code=400, detail="Bike has no weekly rate")
        price = bike.weekly_rate
    else:
        price = bike.daily_rate

    start, end = _extension_dates(rental, body.rate_selected)
    closed = overlapping_full_day_closure(session, start, body.rate_selected)
    if closed is not None:
        raise HTTPException(
            status_code=409,
            detail=closed.message or "The shop is closed on that date",
        )
    if _bike_has_conflict(
        session,
        bike_id=bike.id,
        start=start,
        end=end,
        exclude_rental_id=rental.id,
    ):
        raise HTTPException(
            status_code=409,
            detail="Bike is not available for that extension period",
        )

    payment_status = _payment_state(body)
    extension = Booking(
        user_id=user.id,
        total_price=price,
        amount_paid=Decimal("0.00"),
        payment_method=body.payment_method,
        payment_status=payment_status,
        gcash_ref_no=body.gcash_ref_no,
        gcash_receipt_url=body.gcash_receipt_url,
        expected_pickup_date=start,
        rate_selected=body.rate_selected,
        booking_type=BookingType.extension,
        parent_booking_id=original.id,
        rental_id=rental.id,
        waiver_version=original.waiver_version,
        waiver_accepted_at=original.waiver_accepted_at,
    )
    session.add(extension)
    try:
        session.flush()
        session.add(
            AuditLog(
                actor_id=user.id,
                action="extension.requested",
                target_table="bookings",
                target_id=extension.id,
                details={
                    "rental_id": str(rental.id),
                    "parent_booking_id": str(original.id),
                    "rate": body.rate_selected.value,
                    "price": str(price),
                },
            )
        )
        session.commit()
    except (IntegrityError, DataError) as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=_extension_insert_error(exc),
        ) from exc
    session.refresh(extension)
    return _to_read(extension, [])


@router.post("/staff/extensions/{booking_id}/approve", response_model=BookingRead)
def approve_extension(
    booking_id: uuid.UUID,
    user: StaffUser,
    session: SessionDep,
) -> BookingRead:
    extension = session.exec(
        select(Booking).where(Booking.id == booking_id).with_for_update()
    ).first()
    if extension is None or extension.booking_type != BookingType.extension:
        raise HTTPException(status_code=404, detail="Extension booking not found")
    if extension.extension_applied_at is not None:
        raise HTTPException(status_code=409, detail="Extension is already approved")
    if (
        extension.payment_status != PaymentStatus.paid
        or extension.amount_paid != extension.total_price
    ):
        raise HTTPException(
            status_code=400, detail="Extension requires exact full payment"
        )
    if extension.rental_id is None:
        raise HTTPException(status_code=500, detail="Extension has no rental")

    rental = session.exec(
        select(Rental).where(Rental.id == extension.rental_id).with_for_update()
    ).first()
    if rental is None:
        raise HTTPException(status_code=404, detail="Rental not found")
    if rental.status not in (RentalStatus.active, RentalStatus.overdue):
        raise HTTPException(status_code=400, detail="Rental is not outstanding")

    bike = session.exec(
        select(Bike).where(Bike.id == rental.bike_id).with_for_update()
    ).first()
    if bike is None:
        raise HTTPException(status_code=500, detail="Rental has no bike")
    start, end = _extension_dates(rental, extension.rate_selected)
    if start != extension.expected_pickup_date:
        raise HTTPException(
            status_code=409,
            detail="Rental due time changed; create a new extension request",
        )
    if _bike_has_conflict(
        session,
        bike_id=bike.id,
        start=start,
        end=end,
        exclude_rental_id=rental.id,
    ):
        raise HTTPException(
            status_code=409,
            detail="Bike is no longer available for that extension period",
        )

    now = datetime.now(timezone.utc)
    old_due_at = rental.due_at
    rental.due_at = _extension_due_at(start, extension.rate_selected)
    rental.status = RentalStatus.active
    rental.updated_at = now
    extension.extension_applied_at = now
    extension.updated_at = now
    session.add(
        AuditLog(
            actor_id=user.id,
            action="extension.approved",
            target_table="bookings",
            target_id=extension.id,
            details={
                "rental_id": str(rental.id),
                "old_due_at": ensure_aware(old_due_at).isoformat() if old_due_at else None,
                "new_due_at": rental.due_at.isoformat(),
            },
        )
    )
    session.commit()
    session.refresh(extension)
    return _to_read(extension, [])


def _swap_read(
    row: SwapRequest,
    rental: Rental,
    customer: User | None,
    old_bike: Bike | None,
    new_bike: Bike | None,
) -> SwapRequestRead:
    return SwapRequestRead(
        id=row.id,
        rental_id=row.rental_id,
        reason=row.reason,
        status=row.status,
        new_bike_id=row.new_bike_id,
        handled_by_staff_id=row.handled_by_staff_id,
        customer_name=customer.name if customer else None,
        customer_email=customer.email if customer else None,
        original_bike_id=row.old_bike_id,
        original_bike_name=old_bike.name if old_bike else None,
        new_bike_name=new_bike.name if new_bike else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/rentals/{rental_id}/swap-requests", response_model=SwapRequestRead)
def create_swap_request(
    rental_id: uuid.UUID,
    body: SwapRequestCreate,
    user: CurrentUser,
    session: SessionDep,
) -> SwapRequestRead:
    pair = session.exec(
        select(Rental, Booking)
        .join(Booking, Booking.id == Rental.booking_id)
        .where(Rental.id == rental_id)
        .with_for_update()
    ).first()
    if pair is None or pair[1].user_id != user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    rental, _booking = pair
    if rental.status != RentalStatus.active:
        raise HTTPException(
            status_code=400, detail="Only active rentals can request a swap"
        )
    existing = session.exec(
        select(SwapRequest)
        .where(SwapRequest.rental_id == rental.id)
        .where(SwapRequest.status == SwapStatus.pending)
        .with_for_update()
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A swap request is already pending")

    bike = session.get(Bike, rental.bike_id)
    row = SwapRequest(
        rental_id=rental.id,
        old_bike_id=rental.bike_id,
        reason=body.reason.strip(),
    )
    session.add(row)
    session.flush()
    session.add(
        AuditLog(
            actor_id=user.id,
            action="swap.requested",
            target_table="swap_requests",
            target_id=row.id,
            details={"rental_id": str(rental.id), "bike_id": str(rental.bike_id)},
        )
    )
    session.commit()
    session.refresh(row)
    return _swap_read(row, rental, user, bike, None)


@router.get("/staff/swap-requests", response_model=list[SwapRequestRead])
def list_swap_requests(
    user: StaffUser,
    session: SessionDep,
) -> list[SwapRequestRead]:
    rows = session.exec(
        select(SwapRequest, Rental, Booking, User)
        .join(Rental, Rental.id == SwapRequest.rental_id)
        .join(Booking, Booking.id == Rental.booking_id)
        .join(User, User.id == Booking.user_id)
        .order_by(SwapRequest.created_at.desc())
    ).all()
    result: list[SwapRequestRead] = []
    for request, rental, _booking, customer in rows:
        old_bike = session.get(Bike, rental.bike_id)
        new_bike = session.get(Bike, request.new_bike_id) if request.new_bike_id else None
        result.append(_swap_read(request, rental, customer, old_bike, new_bike))
    return result


@router.post(
    "/staff/swap-requests/{request_id}/decide",
    response_model=SwapRequestRead,
)
def decide_swap_request(
    request_id: uuid.UUID,
    body: SwapDecision,
    user: StaffUser,
    session: SessionDep,
) -> SwapRequestRead:
    row = session.exec(
        select(SwapRequest).where(SwapRequest.id == request_id).with_for_update()
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Swap request not found")
    if row.status != SwapStatus.pending:
        raise HTTPException(status_code=409, detail="Swap request was already decided")

    pair = session.exec(
        select(Rental, Booking)
        .join(Booking, Booking.id == Rental.booking_id)
        .where(Rental.id == row.rental_id)
        .with_for_update()
    ).first()
    if pair is None:
        raise HTTPException(status_code=404, detail="Rental not found")
    rental, booking = pair
    customer = session.get(User, booking.user_id)
    old_bike = session.exec(
        select(Bike).where(Bike.id == rental.bike_id).with_for_update()
    ).first()
    if old_bike is None:
        raise HTTPException(status_code=500, detail="Rental has no bike")

    now = datetime.now(timezone.utc)
    new_bike = None
    if body.decision == "rejected":
        if body.new_bike_id is not None:
            raise HTTPException(
                status_code=400, detail="Rejected swaps cannot include a new bike"
            )
        row.status = SwapStatus.rejected
    else:
        if rental.status != RentalStatus.active:
            raise HTTPException(
                status_code=400, detail="Only active rentals can be swapped"
            )
        if body.new_bike_id is None:
            raise HTTPException(status_code=400, detail="Approval requires new_bike_id")
        if body.new_bike_id == rental.bike_id:
            raise HTTPException(status_code=400, detail="Choose a different bike")
        new_bike = session.exec(
            select(Bike).where(Bike.id == body.new_bike_id).with_for_update()
        ).first()
        if new_bike is None:
            raise HTTPException(status_code=404, detail="Replacement bike not found")
        if new_bike.status != BikeStatus.available:
            raise HTTPException(
                status_code=409, detail="Replacement bike is not available"
            )
        if rental.due_at is None:
            raise HTTPException(status_code=400, detail="Rental has no due time")
        start = now.astimezone(SHOP_TIME_ZONE).date()
        end = ensure_aware(rental.due_at).astimezone(SHOP_TIME_ZONE).date() + timedelta(
            days=1
        )
        if _bike_has_conflict(
            session, bike_id=new_bike.id, start=start, end=end
        ):
            raise HTTPException(
                status_code=409,
                detail="Replacement bike has a conflicting reservation",
            )

        previous_bike_id = rental.bike_id
        old_bike.status = BikeStatus(body.original_bike_status)
        new_bike.status = BikeStatus.rented
        rental.bike_id = new_bike.id
        rental.updated_at = now
        row.new_bike_id = new_bike.id
        row.status = SwapStatus.approved
        session.add(
            AuditLog(
                actor_id=user.id,
                action="swap.approved",
                target_table="swap_requests",
                target_id=row.id,
                details={
                    "rental_id": str(rental.id),
                    "old_bike_id": str(previous_bike_id),
                    "new_bike_id": str(new_bike.id),
                    "old_bike_status": body.original_bike_status,
                },
            )
        )

    row.handled_by_staff_id = user.id
    row.updated_at = now
    if body.decision == "rejected":
        session.add(
            AuditLog(
                actor_id=user.id,
                action="swap.rejected",
                target_table="swap_requests",
                target_id=row.id,
                details={"rental_id": str(rental.id)},
            )
        )
    session.commit()
    session.refresh(row)
    return _swap_read(row, rental, customer, old_bike, new_bike)
