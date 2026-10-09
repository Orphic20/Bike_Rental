import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from bike_rental.lifecycle import (
    no_show_deadline,
    rental_due_at,
    run_lifecycle_sweep,
)
from bike_rental.models import (
    AuditLog,
    Booking,
    PaymentMethod,
    PaymentStatus,
    RateSelected,
    Rental,
    RentalStatus,
)

# jobs.py imports the application database dependency, but creating the engine
# does not connect. Tests call only its pure secret guard.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost:5432/test",
)
from bike_rental.routers.jobs import require_cron_secret


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, *result_sets):
        self.result_sets = list(result_sets)
        self.added = []
        self.commits = 0

    def exec(self, _statement):
        return FakeResult(self.result_sets.pop(0))

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1


def make_booking(
    *,
    payment_method=PaymentMethod.cash,
    payment_status=PaymentStatus.unpaid_pending_pickup,
) -> Booking:
    return Booking(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        total_price=Decimal("100.00"),
        amount_paid=(
            Decimal("100.00")
            if payment_status == PaymentStatus.paid
            else Decimal("0.00")
        ),
        payment_method=payment_method,
        payment_status=payment_status,
        expected_pickup_date=date(2026, 10, 5),
        rate_selected=RateSelected.daily,
    )


def make_rental(
    booking: Booking,
    *,
    status=RentalStatus.reserved,
    due_at=None,
) -> Rental:
    return Rental(
        id=uuid.uuid4(),
        booking_id=booking.id,
        bike_id=uuid.uuid4(),
        price=booking.total_price,
        status=status,
        due_at=due_at,
    )


def test_manila_cutoff_and_due_time_are_stored_as_utc():
    assert no_show_deadline(date(2026, 10, 5)) == datetime(
        2026, 10, 5, 11, tzinfo=timezone.utc
    )
    released = datetime(2026, 10, 5, 2, tzinfo=timezone.utc)
    assert rental_due_at(released, RateSelected.daily) == datetime(
        2026, 10, 5, 11, tzinfo=timezone.utc
    )
    assert rental_due_at(released, RateSelected.weekly) == datetime(
        2026, 10, 11, 11, tzinfo=timezone.utc
    )


def test_sweep_marks_no_show_and_overdue_and_writes_audits():
    booking = make_booking()
    reserved = make_rental(booking)
    active_booking = make_booking(payment_status=PaymentStatus.paid)
    active = make_rental(
        active_booking,
        status=RentalStatus.active,
        due_at=datetime(2026, 10, 5, 11, tzinfo=timezone.utc),
    )
    session = FakeSession([(reserved, booking)], [active])

    result = run_lifecycle_sweep(
        session,
        now=datetime(2026, 10, 5, 11, 5, tzinfo=timezone.utc),
    )

    assert reserved.status == RentalStatus.no_show
    assert booking.payment_status == PaymentStatus.cancelled
    assert active.status == RentalStatus.overdue
    assert result.no_show.updated == 1
    assert result.overdue.updated == 1
    assert session.commits == 1
    assert [item.action for item in session.added if isinstance(item, AuditLog)] == [
        "rental.no_show",
        "rental.overdue",
    ]

    stale_rerun = FakeSession([(reserved, booking)], [active])
    rerun_result = run_lifecycle_sweep(
        stale_rerun,
        now=datetime(2026, 10, 5, 11, 10, tzinfo=timezone.utc),
    )
    assert rerun_result.no_show.updated == 0
    assert rerun_result.overdue.updated == 0
    assert not any(isinstance(item, AuditLog) for item in stale_rerun.added)


def test_paid_no_show_stays_paid_and_pending_verification_is_skipped():
    paid = make_booking(
        payment_method=PaymentMethod.gcash,
        payment_status=PaymentStatus.paid,
    )
    paid_rental = make_rental(paid)
    pending = make_booking(
        payment_method=PaymentMethod.gcash,
        payment_status=PaymentStatus.pending_verification,
    )
    pending_rental = make_rental(pending)
    session = FakeSession(
        [(paid_rental, paid), (pending_rental, pending)],
        [],
    )

    result = run_lifecycle_sweep(
        session,
        now=datetime(2026, 10, 5, 11, 5, tzinfo=timezone.utc),
    )

    assert paid_rental.status == RentalStatus.no_show
    assert paid.payment_status == PaymentStatus.paid
    assert pending_rental.status == RentalStatus.reserved
    assert result.skipped_pending_verification == 1


def test_dry_run_reports_without_mutating_or_committing():
    booking = make_booking()
    rental = make_rental(booking)
    session = FakeSession([(rental, booking)], [])

    result = run_lifecycle_sweep(
        session,
        now=datetime(2026, 10, 5, 11, 5, tzinfo=timezone.utc),
        dry_run=True,
    )

    assert result.no_show.matched == 1
    assert result.no_show.updated == 0
    assert rental.status == RentalStatus.reserved
    assert booking.payment_status == PaymentStatus.unpaid_pending_pickup
    assert session.added == []
    assert session.commits == 0


def test_cron_secret_guard(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    with pytest.raises(HTTPException) as missing:
        require_cron_secret("anything")
    assert missing.value.status_code == 503

    monkeypatch.setenv("CRON_SECRET", "expected")
    with pytest.raises(HTTPException) as invalid:
        require_cron_secret("wrong")
    assert invalid.value.status_code == 401

    assert require_cron_secret("expected") is None
