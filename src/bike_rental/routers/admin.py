"""Bike inventory management, shop open/closed toggle, audit log."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlmodel import select

from bike_rental.auth import AdminUser
from bike_rental.database import SessionDep
from bike_rental.models import (
    Bike,
    BikeCreate,
    BikeRead,
    BikeStatus,
    BikeUpdate,
    Rental,
    RentalStatus,
    ShopSettings,
    ShopSettingsRead,
    ShopStatusLog,
    ShopUpdate,
)
from bike_rental.routers.shop import to_shop_read

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_bike_read(bike: Bike) -> BikeRead:
    return BikeRead(
        id=bike.id,
        name=bike.name,
        type=bike.type,
        status=bike.status,
        daily_rate=bike.daily_rate,
        weekly_rate=bike.weekly_rate,
        image_url=bike.image_url,
        available=(bike.status == BikeStatus.available),
    )


@router.get("/bikes", response_model=list[BikeRead])
def list_admin_bikes(
    user: AdminUser,
    session: SessionDep,
) -> list[BikeRead]:
    bikes = session.exec(select(Bike).order_by(Bike.name)).all()
    return [_to_bike_read(bike) for bike in bikes]


@router.post("/bikes", response_model=BikeRead)
def create_bike(
    user: AdminUser,
    session: SessionDep,
    body: BikeCreate,
) -> BikeRead:
    if body.status == BikeStatus.rented:
        raise HTTPException(status_code=400, detail="Cannot create a bike as rented")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    taken = session.exec(
        select(Bike).where(func.lower(Bike.name) == name.lower())
    ).first()
    if taken:
        raise HTTPException(status_code=409, detail="A bike with this name already exists")
    bike = Bike(
        name=name,
        type=body.type,
        daily_rate=body.daily_rate,
        weekly_rate=body.weekly_rate,
        image_url=body.image_url,
        status=body.status,
    )
    session.add(bike)
    session.commit()
    session.refresh(bike)
    return _to_bike_read(bike)


@router.patch("/bikes/{bike_id}", response_model=BikeRead)
def update_bike(
    bike_id: uuid.UUID,
    body: BikeUpdate,
    user: AdminUser,
    session: SessionDep,
) -> BikeRead:
    bike = session.get(Bike, bike_id)
    if bike is None:
        raise HTTPException(status_code=404, detail="Bike not found")
    if body.status == BikeStatus.rented:
        raise HTTPException(status_code=400, detail="Cannot set a bike as rented")

    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        taken = session.exec(
            select(Bike).where(
                func.lower(Bike.name) == name.lower(),
                Bike.id != bike.id,
            )
        ).first()
        if taken:
            raise HTTPException(
                status_code=409,
                detail="A bike with this name already exists",
            )
        data["name"] = name

    if "status" in data:
        outstanding = session.exec(
            select(Rental).where(
                Rental.bike_id == bike.id,
                Rental.status.in_((RentalStatus.active, RentalStatus.overdue)),
            )
        ).first()
        if outstanding:
            raise HTTPException(
                status_code=400,
                detail="Cannot change status while the bike is out",
            )

    for key, value in data.items():
        setattr(bike, key, value)
    session.add(bike)
    session.commit()
    session.refresh(bike)
    return _to_bike_read(bike)

@router.put("/shop/settings", response_model=ShopSettingsRead)
def update_shop_settings(
    body: ShopUpdate,
    user: AdminUser,
    session: SessionDep,
) -> ShopSettingsRead:
    settings = session.get(ShopSettings, 1)
    if settings is None:
        raise HTTPException(status_code=404, detail="Shop settings not found")
    settings.is_open = body.is_open
    session.add(settings)
    session.flush()

    reason = (body.reason or "").strip() or None
    log = session.exec(
        select(ShopStatusLog).order_by(ShopStatusLog.created_at.desc())
    ).first()
    if log:
        if not body.is_open and reason:
            log.reason = reason
        log.changed_by_admin_id = user.id
        session.add(log)

    session.commit()
    session.refresh(settings)
    return to_shop_read(session, settings)