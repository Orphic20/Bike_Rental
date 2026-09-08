"""Profile, name confirmation, ToS acceptance."""

from fastapi import APIRouter, HTTPException

from bike_rental.auth import CurrentUser
from bike_rental.database import SessionDep
from bike_rental.models import Role, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser, session: SessionDep) -> UserRead:
    role = session.get(Role, user.role_id)
    if role is None:
        raise HTTPException(status_code=500, detail="User has no role")
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        role=role.name,
        created_at=user.created_at,
        name_confirmed=user.name_confirmed,
        tos_version_accepted=user.tos_version_accepted,
        tos_accepted_at=user.tos_accepted_at,
        is_active=user.is_active,
    )
