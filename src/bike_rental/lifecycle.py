"""Idempotent rental lifecycle transitions shared by manual and scheduled jobs."""

import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, or_, select

from bike_rental.availability import ensure_aware, span_days
from bike_rental.models import (
    AuditLog,
    AuditPurgeRead,
    Booking,
    LifecycleSweepRead,
    LifecycleTransitionRead,
    PaymentMethod,
    PaymentStatus,
    RateSelected,
    ReceiptPurgeRead,
    Rental,
    RentalStatus,
)
from bike_rental.routers.uploads import delete_cloudinary_image

SHOP_TIME_ZONE = ZoneInfo("Asia/Manila")
SHOP_OPENING_TIME = time(8, 0)
SHOP_CLOSING_TIME = time(19, 0)
RECEIPT_FOLDER = "munoz/receipts"
RECEIPT_RETENTION = timedelta(days=30)
RECEIPT_PURGE_LIMIT = 10
RECEIPT_PURGE_BUDGET = timedelta(seconds=25)
AUDIT_RETENTION = timedelta(days=182)
AUDIT_PURGE_LIMIT = 200

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
    """Return 7 PM Manila on the final day of the selected rental period.

    A range lower bound cannot be after the upper bound. If staff release after
    closing on the last day, roll due to the next 7 PM so the bike can still go
    out.
    """
    released_local = ensure_aware(released_at).astimezone(SHOP_TIME_ZONE)
    final_date = released_local.date() + timedelta(days=span_days(rate) - 1)
    local_due = datetime.combine(final_date, SHOP_CLOSING_TIME, tzinfo=SHOP_TIME_ZONE)
    if local_due <= released_local:
        local_due += timedelta(days=1)
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


def _purge_stale_gcash_receipts(
    session: Session,
    *,
    run_at: datetime,
    dry_run: bool,
    delete_receipt: Callable[..., bool],
) -> ReceiptPurgeRead:
    """Remove Cloudinary GCash images and reference numbers older than 1 month."""
    cutoff = run_at - RECEIPT_RETENTION
    rows = session.exec(
        select(Booking)
        .where(Booking.payment_method == PaymentMethod.gcash)
        .where(Booking.created_at.is_not(None))
        .where(Booking.created_at <= cutoff)
        .where(
            or_(
                Booking.gcash_receipt_url.is_not(None),
                Booking.gcash_ref_no.is_not(None),
            )
        )
        .order_by(Booking.id)
        .limit(RECEIPT_PURGE_LIMIT)
    ).all()

    matched_ids: list[uuid.UUID] = []
    skipped_pending = 0
    skipped_failed = 0
    updated = 0

    deadline = datetime.now(timezone.utc) + RECEIPT_PURGE_BUDGET
    for booking in rows:
        if booking.created_at is None:
            continue
        if ensure_aware(booking.created_at) > cutoff:
            continue
        if not booking.gcash_receipt_url and not booking.gcash_ref_no:
            continue
        if booking.payment_status == PaymentStatus.pending_verification:
            skipped_pending += 1
            continue
        matched_ids.append(booking.id)
        if dry_run:
            continue
        if datetime.now(timezone.utc) >= deadline:
            break
        receipt_url = booking.gcash_receipt_url
        if receipt_url and not delete_receipt(receipt_url, folder=RECEIPT_FOLDER):
            skipped_failed += 1
            continue
        booking.gcash_receipt_url = None
        booking.gcash_ref_no = None
        booking.updated_at = run_at
        session.add(booking)
        session.add(
            AuditLog(
                actor_id=None,
                action="booking.receipt_purged",
                target_table="bookings",
                target_id=booking.id,
                details={
                    "booking_ref": booking.booking_ref,
                    "created_at": ensure_aware(booking.created_at).isoformat(),
                },
            )
        )
        updated += 1

    return ReceiptPurgeRead(
        matched=len(matched_ids),
        updated=updated,
        skipped_pending_verification=skipped_pending,
        skipped_failed=skipped_failed,
        booking_ids=matched_ids,
    )


def _purge_stale_audit_logs(
    session: Session,
    *,
    run_at: datetime,
    dry_run: bool,
) -> AuditPurgeRead:
    """Delete audit rows older than 6 months. Do not write a replacement log."""
    cutoff = run_at - AUDIT_RETENTION
    rows = session.exec(
        select(AuditLog)
        .where(AuditLog.created_at.is_not(None))
        .where(AuditLog.created_at <= cutoff)
        .order_by(AuditLog.created_at, AuditLog.id)
        .limit(AUDIT_PURGE_LIMIT)
    ).all()

    matched: list[AuditLog] = []
    for log in rows:
        if log.created_at is None:
            continue
        if ensure_aware(log.created_at) > cutoff:
            continue
        matched.append(log)

    if not dry_run:
        for log in matched:
            session.delete(log)

    return AuditPurgeRead(
        matched=len(matched),
        updated=0 if dry_run else len(matched),
        audit_ids=[log.id for log in matched],
    )


def run_lifecycle_sweep(
    session: Session,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    delete_receipt: Callable[..., bool] | None = None,
) -> LifecycleSweepRead:
    """Mark no-shows and overdue rentals, then drop old receipts and audits."""
    run_at = ensure_aware(now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    reserved_rows = session.exec(
        select(Rental, Booking)
        .join(Booking, Booking.id == Rental.booking_id)
        .where(Rental.status == RentalStatus.reserved)
        .where(Rental.released_at.is_(None))
        .where(Booking.expected_pickup_date <= run_at.astimezone(SHOP_TIME_ZONE).date())
        .order_by(Rental.id)
        .with_for_update(skip_locked=True)
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
        .with_for_update(skip_locked=True)
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

    if not dry_run and (no_show_updated or overdue_updated):
        session.commit()

    receipts = _purge_stale_gcash_receipts(
        session,
        run_at=run_at,
        dry_run=dry_run,
        delete_receipt=delete_receipt or delete_cloudinary_image,
    )

    if not dry_run and receipts.updated:
        session.commit()

    audits = _purge_stale_audit_logs(session, run_at=run_at, dry_run=dry_run)
    if not dry_run and audits.updated:
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
        receipts=receipts,
        audits=audits,
    )
