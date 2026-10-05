"""Public shop open/closed flag and scheduled closures."""

from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session, select

from bike_rental.availability import (
    closure_effective_window,
    dates_covered,
    effective_window,
    windows_overlap,
)
from bike_rental.database import SessionDep
from bike_rental.models import (
    ShopClosure,
    ShopClosureRead,
    ShopSettings,
    ShopSettingsRead,
    ShopStatusLog,
)

router = APIRouter(prefix="/shop", tags=["shop"])


def to_shop_read(session: Session, settings: ShopSettings) -> ShopSettingsRead:
    reason = None
    if not settings.is_open:
        log = session.exec(
            select(ShopStatusLog)
            .where(ShopStatusLog.is_open.is_(False))
            .order_by(ShopStatusLog.created_at.desc())
        ).first()
        reason = log.reason if log else None
    return ShopSettingsRead(
        is_open=settings.is_open,
        updated_at=settings.updated_at,
        reason=reason,
        schedule_override_until=settings.schedule_override_until,
    )


def to_closure_read(row: ShopClosure) -> ShopClosureRead:
    effective_start, effective_end = effective_window(
        row.starts_at,
        row.ends_at,
        row.buffer_before_min,
        row.buffer_after_min,
    )
    return ShopClosureRead(
        id=row.id,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        effective_starts_at=effective_start,
        effective_ends_at=effective_end,
        kind=row.kind,
        buffer_before_min=row.buffer_before_min,
        buffer_after_min=row.buffer_after_min,
        message=row.message,
        created_by_admin_id=row.created_by_admin_id,
        created_at=row.created_at,
    )


def closures_overlapping(
    session: Session,
    range_start: date,
    range_end: date,
) -> list[ShopClosureRead]:
    rows = session.exec(
        select(ShopClosure).order_by(ShopClosure.starts_at)
    ).all()
    return [
        to_closure_read(row)
        for row in rows
        if windows_overlap(
            range_start,
            range_end,
            *dates_covered(*closure_effective_window(row)),
        )
    ]


@router.get("/settings", response_model=ShopSettingsRead)
def read_shop_settings(session: SessionDep) -> ShopSettingsRead:
    settings = session.get(ShopSettings, 1)
    if settings is None:
        raise HTTPException(status_code=404, detail="Shop settings not found")
    return to_shop_read(session, settings)


@router.get("/closures", response_model=list[ShopClosureRead])
def list_shop_closures(
    session: SessionDep,
    start: Annotated[
        Optional[date],
        Query(description="Inclusive start date (UTC calendar). Defaults to today."),
    ] = None,
    end: Annotated[
        Optional[date],
        Query(description="Exclusive end date. Defaults to start + 90 days."),
    ] = None,
) -> list[ShopClosureRead]:
    today = datetime.now(timezone.utc).date()
    range_start = start or today
    range_end = end or (range_start + timedelta(days=90))
    if range_end <= range_start:
        raise HTTPException(status_code=400, detail="end must be after start")
    return closures_overlapping(session, range_start, range_end)
