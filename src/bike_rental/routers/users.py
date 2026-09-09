"""Profile, name confirmation, ToS acceptance."""

from fastapi import APIRouter

from bike_rental.auth import CurrentRole, CurrentUser
from bike_rental.models import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser, role: CurrentRole) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        role=role,
        created_at=user.created_at,
        name_confirmed=user.name_confirmed,
        tos_version_accepted=user.tos_version_accepted,
        tos_accepted_at=user.tos_accepted_at,
        is_active=user.is_active,
    )
