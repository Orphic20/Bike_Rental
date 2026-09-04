"""Bike inventory management, shop open/closed toggle, audit log."""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
