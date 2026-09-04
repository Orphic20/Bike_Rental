"""GCash receipt verification and cash-on-pickup settlement."""

from fastapi import APIRouter

router = APIRouter(prefix="/payments", tags=["payments"])
