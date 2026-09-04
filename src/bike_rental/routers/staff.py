"""Counter workflow: search, release, return, bike status changes."""

from fastapi import APIRouter

router = APIRouter(prefix="/staff", tags=["staff"])
