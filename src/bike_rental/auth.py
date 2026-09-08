import os
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from typing import Annotated

from bike_rental.models import User
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