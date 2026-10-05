"""Date-window arithmetic shared by the catalogue and the booking endpoints.

A reservation is stored as a pickup date plus a rate, not as an explicit range,
so the occupied window has to be derived. Both /bikes and /bookings need the
same derivation, and they must agree or the catalogue will advertise a bike the
booking endpoint then rejects with a 409.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import Session, select

from bike_rental.models import (
    Booking,
    ClosureKind,
    RateSelected,
    Rental,
    RentalStatus,
    ShopClosure,
    ShopSettings,
    User,
)

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


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def effective_window(
    starts_at: datetime,
    ends_at: datetime,
    buffer_before_min: int,
    buffer_after_min: int,
) -> tuple[datetime, datetime]:
    """Counter blackout: event range padded by the admin-chosen buffers."""
    start = ensure_aware(starts_at) - timedelta(minutes=buffer_before_min)
    end = ensure_aware(ends_at) + timedelta(minutes=buffer_after_min)
    return start, end


def closure_effective_window(closure: ShopClosure) -> tuple[datetime, datetime]:
    return effective_window(
        closure.starts_at,
        closure.ends_at,
        closure.buffer_before_min,
        closure.buffer_after_min,
    )


def dates_covered(start: datetime, end: datetime) -> tuple[date, date]:
    """Half-open calendar dates touched by a timestamptz range.

    A 1:00–3:00 PM window on Oct 25 becomes [Oct 25, Oct 26). A full-day
    block stored as [Oct 25 00:00, Oct 28 00:00) stays [Oct 25, Oct 28).
    """
    start = ensure_aware(start)
    end = ensure_aware(end)
    d0 = start.date()
    midnight = datetime.combine(end.date(), time.min, tzinfo=end.tzinfo)
    d1 = end.date() if end == midnight else end.date() + timedelta(days=1)
    return d0, d1


def conflicting_bookings(
    session: Session,
    range_start: datetime,
    range_end: datetime,
) -> list[tuple[Booking, User]]:
    """Bookings whose hold overlaps the calendar dates of [range_start, range_end)."""
    d0, d1 = dates_covered(range_start, range_end)
    rows = session.exec(
        select(Rental, Booking, User)
        .join(Booking, Booking.id == Rental.booking_id)
        .join(User, User.id == Booking.user_id)
        .where(Rental.status.in_(BLOCKING_STATUSES))
    ).all()
    by_id: dict[uuid.UUID, tuple[Booking, User]] = {}
    for rental, booking, user in rows:
        if windows_overlap(d0, d1, *existing_window(rental, booking)):
            by_id[booking.id] = (booking, user)
    return list(by_id.values())


def overlapping_full_day_closure(
    session: Session,
    pickup_date: date,
    rate: RateSelected,
) -> ShopClosure | None:
    """A full-day blockout that collides with this pickup window.

    Hours-only closures are desk blackouts; they must not reject POST /bookings.
    """
    new_start, new_end = window(pickup_date, rate)
    rows = session.exec(
        select(ShopClosure).where(ShopClosure.kind == ClosureKind.full_day)
    ).all()
    for closure in rows:
        covered = dates_covered(*closure_effective_window(closure))
        if windows_overlap(new_start, new_end, *covered):
            return closure
    return None


def counter_closed_detail(
    session: Session,
    now: datetime | None = None,
) -> str | None:
    """Why the desk cannot release, return, or take cash right now.

    Panic close (is_open false) always wins. Hours closures apply unless
    schedule_override_until is still in the future. Full-day rows do not
    belong here — they already 409 POST /bookings.
    """
    now = ensure_aware(now or datetime.now(timezone.utc))
    settings = session.get(ShopSettings, 1)
    if settings is not None and not settings.is_open:
        return "The shop is closed"

    override = (
        ensure_aware(settings.schedule_override_until)
        if settings is not None and settings.schedule_override_until is not None
        else None
    )
    if override is not None and now < override:
        return None

    rows = session.exec(
        select(ShopClosure).where(ShopClosure.kind == ClosureKind.hours)
    ).all()
    for closure in rows:
        start, end = closure_effective_window(closure)
        if start <= now < end:
            until = end.isoformat()
            message = (closure.message or "").strip()
            if message:
                return f"Counter closed until {until}: {message}"
            return f"Counter closed until {until}"
    return None


def current_hours_override_until(
    session: Session,
    now: datetime | None = None,
) -> datetime | None:
    """Latest effective_end of any hours closure that currently covers now."""
    now = ensure_aware(now or datetime.now(timezone.utc))
    latest: datetime | None = None
    rows = session.exec(
        select(ShopClosure).where(ShopClosure.kind == ClosureKind.hours)
    ).all()
    for closure in rows:
        start, end = closure_effective_window(closure)
        if start <= now < end:
            if latest is None or end > latest:
                latest = end
    return latest
