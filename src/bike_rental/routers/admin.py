"""Bike inventory management, shop open/closed toggle, audit log."""

from fastapi import APIRouter
from sqlmodel import select

from bike_rental.auth import AdminUser
from bike_rental.database import SessionDep
from bike_rental.models import Bike, BikeRead, BikeStatus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/bikes", response_model=list[BikeRead])
def list_admin_bikes(
    user: AdminUser,
    session: SessionDep,
) -> list[BikeRead]:
    bikes = session.exec(select(Bike).order_by(Bike.name)).all()
    return [
        BikeRead(
            id=bike.id,
            name=bike.name,
            type=bike.type,
            status=bike.status,
            daily_rate=bike.daily_rate,
            weekly_rate=bike.weekly_rate,
            image_url=bike.image_url,
            available=(bike.status == BikeStatus.available),
        )
        for bike in bikes
    ]
