"""Bike inventory management, shop open/closed toggle, audit log."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlmodel import select

from bike_rental.auth import AdminUser
from bike_rental.database import SessionDep
from bike_rental.models import Bike, BikeRead, BikeStatus, BikeCreate, BikeUpdate

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
