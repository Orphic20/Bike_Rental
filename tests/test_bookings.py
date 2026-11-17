from datetime import date, time

import pytest
from pydantic import ValidationError

from bike_rental.lifecycle import SHOP_CLOSING_TIME, SHOP_OPENING_TIME
from bike_rental.models import BookingCreate, BookingItemCreate, PaymentMethod, RateSelected


def _payload(**overrides):
    body = {
        "bikes": [BookingItemCreate(bike_id="00000000-0000-0000-0000-000000000001")],
        "expected_pickup_date": date(2026, 11, 17),
        "expected_pickup_time": time(9, 30),
        "rate_selected": RateSelected.daily,
        "payment_method": PaymentMethod.cash,
        "waiver_version": "1.0",
    }
    body.update(overrides)
    return body


def test_booking_create_requires_pickup_time():
    payload = _payload()
    del payload["expected_pickup_time"]
    with pytest.raises(ValidationError):
        BookingCreate(**payload)


def test_shop_hours_cover_estimated_pickup_slots():
    assert SHOP_OPENING_TIME == time(8, 0)
    assert SHOP_CLOSING_TIME == time(19, 0)
    assert SHOP_OPENING_TIME <= time(9, 30) <= SHOP_CLOSING_TIME
