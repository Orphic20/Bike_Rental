import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost:5432/test",
)

from bike_rental.models import (
    Booking,
    BookingType,
    ExtensionCreate,
    PaymentMethod,
    PaymentStatus,
    RateSelected,
    Rental,
    RentalStatus,
)
from bike_rental.routers.extensions_swaps import (
    _bike_has_conflict,
    _extension_dates,
    _extension_due_at,
    _payment_state,
)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def exec(self, _statement):
        return FakeResult(self.rows)


def booking(*, pickup: date, rate: RateSelected) -> Booking:
    return Booking(
        user_id=uuid.uuid4(),
        total_price=Decimal("100.00"),
        payment_method=PaymentMethod.cash,
        payment_status=PaymentStatus.paid,
        expected_pickup_date=pickup,
        rate_selected=rate,
        booking_type=BookingType.new,
    )


def rental(*, bike_id: uuid.UUID, due_at: datetime | None = None) -> Rental:
    return Rental(
        booking_id=uuid.uuid4(),
        bike_id=bike_id,
        released_at=datetime(2026, 10, 15, 2, tzinfo=timezone.utc),
        due_at=due_at,
        price=Decimal("100.00"),
        status=RentalStatus.active,
    )


def test_extension_starts_day_after_due_and_keeps_manila_cutoff():
    row = rental(
        bike_id=uuid.uuid4(),
        due_at=datetime(2026, 10, 15, 11, tzinfo=timezone.utc),
    )

    start, end = _extension_dates(row, RateSelected.weekly)

    assert start == date(2026, 10, 16)
    assert end == date(2026, 10, 23)
    assert _extension_due_at(start, RateSelected.weekly) == datetime(
        2026, 10, 22, 11, tzinfo=timezone.utc
    )


def test_extension_availability_detects_overlapping_reservation():
    bike_id = uuid.uuid4()
    existing = rental(bike_id=bike_id)
    existing.released_at = None
    existing.due_at = None
    parent = booking(pickup=date(2026, 10, 16), rate=RateSelected.daily)

    assert _bike_has_conflict(
        FakeSession([(existing, parent)]),
        bike_id=bike_id,
        start=date(2026, 10, 16),
        end=date(2026, 10, 17),
    )


def test_extension_availability_ignores_the_rental_being_extended():
    bike_id = uuid.uuid4()
    current = rental(
        bike_id=bike_id,
        due_at=datetime(2026, 10, 15, 11, tzinfo=timezone.utc),
    )
    parent = booking(pickup=date(2026, 10, 15), rate=RateSelected.daily)

    assert not _bike_has_conflict(
        FakeSession([(current, parent)]),
        bike_id=bike_id,
        start=date(2026, 10, 16),
        end=date(2026, 10, 17),
        exclude_rental_id=current.id,
    )


def test_gcash_extension_requires_both_proof_fields():
    with pytest.raises(HTTPException, match="GCash requires"):
        _payment_state(
            ExtensionCreate(
                rate_selected=RateSelected.daily,
                payment_method=PaymentMethod.gcash,
                gcash_ref_no="123",
            )
        )


def test_cash_extension_rejects_gcash_fields():
    with pytest.raises(HTTPException, match="Cash extensions"):
        _payment_state(
            ExtensionCreate(
                rate_selected=RateSelected.daily,
                payment_method=PaymentMethod.cash,
                gcash_ref_no="123",
            )
        )
