"""Browsing the catalogue and checking availability for a pickup date."""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Query
from sqlmodel import select

from bike_rental.availability import unavailable_bike_ids
from bike_rental.database import SessionDep
from bike_rental.models import (
    Bike,
    BikeRead,
    BikeStatus,
    BikeType,
    RateSelected,
)

router = APIRouter(prefix="/bikes", tags=["bikes"])


@router.get("", response_model=list[BikeRead])
def list_bikes(
    session: SessionDep,
    type: Annotated[Optional[BikeType], Query()] = None,
    pickup_date: Annotated[
        Optional[date],
        Query(description="Mark bikes already reserved for this date as unavailable."),
    ] = None,
    rate: Annotated[RateSelected, Query()] = RateSelected.daily,
) -> list[BikeRead]:
    # Retired bikes are gone for good; showing them would only produce a 409 at
    # booking time.
    statement = select(Bike).where(Bike.status != BikeStatus.retired)
    if type is not None:
        statement = statement.where(Bike.type == type)
    bikes = session.exec(statement.order_by(Bike.name)).all()

    taken: set = set()
    if pickup_date is not None:
        taken = unavailable_bike_ids(session, pickup_date, rate)

    return [
        BikeRead(
            id=bike.id,
            name=bike.name,
            type=bike.type,
            status=bike.status,
            daily_rate=bike.daily_rate,
            weekly_rate=bike.weekly_rate,
            image_url=bike.image_url,
            available=(
                bike.status == BikeStatus.available and bike.id not in taken
            ),
        )
        for bike in bikes
    ]
