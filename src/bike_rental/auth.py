import os
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from typing import Annotated

from bike_rental.models import Role, RoleName, User
from bike_rental.database import SessionDep

bearer = HTTPBearer(auto_error=False)

# New Supabase projects sign user tokens with ES256. The public key is in JWKS,
# not SUPABASE_JWT_SECRET (that secret is HS256-only and will not verify these).
JWKS_URL = os.getenv(
    "SUPABASE_JWKS_URL",
    "https://eqvzbsnywygzcxauxcyj.supabase.co/auth/v1/.well-known/jwks.json",
)
_jwks_client = jwt.PyJWKClient(JWKS_URL)


def get_current_user(
    session: SessionDep,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    token = creds.credentials if creds else None
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Not authenticated: {exc} (chars={len(token)})",
        )

    sub = payload["sub"]
    user = session.exec(select(User).where(User.id == uuid.UUID(sub))).first()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_role(user: CurrentUser, session: SessionDep) -> RoleName:
    role = session.get(Role, user.role_id)
    if role is None:
        raise HTTPException(status_code=500, detail="User has no role")
    return role.name


# FastAPI caches a dependency per request, so several guards on one endpoint
# still cost a single role lookup.
CurrentRole = Annotated[RoleName, Depends(get_current_role)]


def require_role(*allowed: RoleName):
    """Build a dependency that rejects callers outside `allowed`.

    Roles do not nest: admin only passes a staff guard if staff and admin are
    both listed.
    """

    def dependency(user: CurrentUser, role: CurrentRole) -> User:
        if role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {' or '.join(r.value for r in allowed)} role",
            )
        return user

    return dependency


StaffUser = Annotated[User, Depends(require_role(RoleName.staff, RoleName.admin))]
AdminUser = Annotated[User, Depends(require_role(RoleName.admin))]