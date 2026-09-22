"""Public shop open/closed flag."""

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from bike_rental.database import SessionDep
from bike_rental.models import ShopSettings, ShopSettingsRead, ShopStatusLog

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
    )


@router.get("/settings", response_model=ShopSettingsRead)
def read_shop_settings(session: SessionDep) -> ShopSettingsRead:
    settings = session.get(ShopSettings, 1)
    if settings is None:
        raise HTTPException(status_code=404, detail="Shop settings not found")
    return to_shop_read(session, settings)
