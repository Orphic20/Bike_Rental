"""Date-window arithmetic shared by the catalogue and the booking endpoints.

A reservation is stored as a pickup date plus a rate, not as an explicit range,
so the occupied window has to be derived. Both /bikes and /bookings need the
same derivation, and they must agree or the catalogue will advertise a bike the
booking endpoint then rejects with a 409.
"""

import uuid
from datetime import date, timedelta

from sqlmodel import Session, select

from bike_rental.models import Booking, RateSelected, Rental, RentalStatus

# A rental in any of these states still holds its bike; returned/cancelled/no_show
# ones have released it.
BLOCKING_STATUSES = (
    RentalStatus.reserved,
    RentalStatus.active,
    RentalStatus.overdue,
)


def span_days(rate: RateSelected) -> int:
    return 7 if rate == RateSelected.weekly else 1


def window(start: date, rate: RateSelected) -> tuple[date, date]:
    """Half-open [start, end): daily = 1 day, weekly = 7 days."""
    return start, start + timedelta(days=span_days(rate))


def windows_overlap(a0: date, a1: date, b0: date, b1: date) -> bool:
    return a0 < b1 and b0 < a1


def existing_window(rental: Rental, parent: Booking) -> tuple[date, date]:
    """The window a rental actually occupies.

    Once staff releases a bike the real dates are known, so they win over the
    booking's estimate. due_at is an inclusive instant, hence the +1 day to make
    the range half-open like the others.
    """
    if rental.released_at is not None:
        start = rental.released_at.date()
        if rental.due_at is not None:
            return start, rental.due_at.date() + timedelta(days=1)
        return window(start, parent.rate_selected)
    return window(parent.expected_pickup_date, parent.rate_selected)


def unavailable_bike_ids(
    session: Session,
    pickup_date: date,
    rate: RateSelected,
) -> set[uuid.UUID]:
    """Bikes already spoken for during the window starting at pickup_date.

    One query for the whole catalogue rather than one per bike, since the
    listing endpoint would otherwise fan out across the fleet.
    """
    new_start, new_end = window(pickup_date, rate)

    rows = session.exec(
        select(Rental, Booking)
        .join(Booking, Booking.id == Rental.booking_id)
        .where(Rental.status.in_(BLOCKING_STATUSES))
    ).all()

    return {
        rental.bike_id
        for rental, parent in rows
        if windows_overlap(new_start, new_end, *existing_window(rental, parent))
    }
