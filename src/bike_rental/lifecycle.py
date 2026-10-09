"""Idempotent rental lifecycle transitions shared by manual and scheduled jobs."""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from bike_rental.availability import ensure_aware, span_days
from bike_rental.models import (
    AuditLog,
    Booking,
    LifecycleSweepRead,
    LifecycleTransitionRead,
    PaymentMethod,
    PaymentStatus,
    RateSelected,
    Rental,
    RentalStatus,
)

SHOP_TIME_ZONE = ZoneInfo("Asia/Manila")
SHOP_CLOSING_TIME = time(19, 0)

NO_SHOW_PAYMENT_STATUSES = (
    PaymentStatus.unpaid_pending_pickup,
    PaymentStatus.paid,
    PaymentStatus.rejected,
)


def no_show_deadline(pickup_date: date) -> datetime:
    """Return the pickup-day 7 PM cutoff as an aware UTC datetime."""
    local = datetime.combine(pickup_date, SHOP_CLOSING_TIME, tzinfo=SHOP_TIME_ZONE)
    return local.astimezone(timezone.utc)


def rental_due_at(released_at: datetime, rate: RateSelected) -> datetime:
    """Return 7 PM Manila on the final day of the selected rental period."""
    released_local = ensure_aware(released_at).astimezone(SHOP_TIME_ZONE)
    final_date = released_local.date() + timedelta(days=span_days(rate) - 1)
    local_due = datetime.combine(final_date, SHOP_CLOSING_TIME, tzinfo=SHOP_TIME_ZONE)
    return local_due.astimezone(timezone.utc)


def _audit(
    session: Session,
    *,
    action: str,
    rental: Rental,
    details: dict,
) -> None:
    session.add(
        AuditLog(
            actor_id=None,
            action=action,
            target_table="rentals",
            target_id=rental.id,
            details=details,
        )
    )


def run_lifecycle_sweep(
    session: Session,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> LifecycleSweepRead:
    """Mark pickup no-shows and overdue rentals in one race-safe transaction."""
    run_at = ensure_aware(now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    reserved_rows = session.exec(
        select(Rental, Booking)
        .join(Booking, Booking.id == Rental.booking_id)
        .where(Rental.status == RentalStatus.reserved)
        .where(Rental.released_at.is_(None))
        .where(Booking.expected_pickup_date <= run_at.astimezone(SHOP_TIME_ZONE).date())
        .order_by(Rental.id)
        .with_for_update()
    ).all()

    no_show_rows: list[tuple[Rental, Booking]] = []
    skipped_pending = 0
    for rental, booking in reserved_rows:
        if booking.payment_status == PaymentStatus.pending_verification:
            if run_at >= no_show_deadline(booking.expected_pickup_date):
                skipped_pending += 1
            continue
        if booking.payment_status not in NO_SHOW_PAYMENT_STATUSES:
            continue
        if run_at >= no_show_deadline(booking.expected_pickup_date):
            no_show_rows.append((rental, booking))

    overdue_rows = session.exec(
        select(Rental)
        .where(Rental.status == RentalStatus.active)
        .where(Rental.returned_at.is_(None))
        .where(Rental.due_at.is_not(None))
        .where(Rental.due_at < run_at)
        .order_by(Rental.id)
        .with_for_update()
    ).all()

    no_show_ids = [rental.id for rental, _ in no_show_rows]
    overdue_ids = [rental.id for rental in overdue_rows]
    no_show_updated = 0
    overdue_updated = 0

    if not dry_run:
        original_payment_statuses = {
            booking.id: booking.payment_status for _, booking in no_show_rows
        }
        cancelled_bookings: set[uuid.UUID] = set()
        for rental, booking in no_show_rows:
            if rental.status != RentalStatus.reserved or rental.released_at is not None:
                continue
            rental.status = RentalStatus.no_show
            rental.updated_at = run_at
            session.add(rental)

            if (
                booking.payment_method == PaymentMethod.cash
                and booking.payment_status == PaymentStatus.unpaid_pending_pickup
                and booking.id not in cancelled_bookings
            ):
                booking.payment_status = PaymentStatus.cancelled
                booking.updated_at = run_at
                session.add(booking)
                cancelled_bookings.add(booking.id)

            _audit(
                session,
                action="rental.no_show",
                rental=rental,
                details={
                    "booking_id": str(booking.id),
                    "booking_ref": booking.booking_ref,
                    "pickup_date": booking.expected_pickup_date.isoformat(),
                    "cutoff": no_show_deadline(booking.expected_pickup_date).isoformat(),
                    "payment_status": original_payment_statuses[booking.id].value,
                },
            )
            no_show_updated += 1

        for rental in overdue_rows:
            if (
                rental.status != RentalStatus.active
                or rental.returned_at is not None
                or rental.due_at is None
                or ensure_aware(rental.due_at) >= run_at
            ):
                continue
            rental.status = RentalStatus.overdue
            rental.updated_at = run_at
            session.add(rental)
            _audit(
                session,
                action="rental.overdue",
                rental=rental,
                details={
                    "booking_id": str(rental.booking_id),
                    "due_at": ensure_aware(rental.due_at).isoformat(),
                },
            )
            overdue_updated += 1

        session.commit()

    return LifecycleSweepRead(
        dry_run=dry_run,
        run_at=run_at,
        skipped_pending_verification=skipped_pending,
        no_show=LifecycleTransitionRead(
            matched=len(no_show_rows),
            updated=no_show_updated,
            rental_ids=no_show_ids,
        ),
        overdue=LifecycleTransitionRead(
            matched=len(overdue_rows),
            updated=overdue_updated,
            rental_ids=overdue_ids,
        ),
    )
