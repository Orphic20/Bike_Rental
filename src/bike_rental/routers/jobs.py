"""Manual and scheduled entry points for rental lifecycle automation."""

import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from bike_rental.auth import AdminUser
from bike_rental.database import SessionDep
from bike_rental.lifecycle import run_lifecycle_sweep
from bike_rental.models import LifecycleSweepRead

router = APIRouter(tags=["jobs"])


def require_cron_secret(
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.getenv("CRON_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="Lifecycle automation is not configured")
    if x_cron_secret is None or not secrets.compare_digest(x_cron_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid cron secret")


@router.post("/admin/jobs/lifecycle-sweep", response_model=LifecycleSweepRead)
def run_admin_lifecycle_sweep(
    _user: AdminUser,
    session: SessionDep,
    dry_run: bool = Query(default=True),
) -> LifecycleSweepRead:
    return run_lifecycle_sweep(session, dry_run=dry_run)


@router.post("/internal/jobs/lifecycle-sweep", response_model=LifecycleSweepRead)
def run_scheduled_lifecycle_sweep(
    session: SessionDep,
    _: None = Depends(require_cron_secret),
) -> LifecycleSweepRead:
    return run_lifecycle_sweep(session)
