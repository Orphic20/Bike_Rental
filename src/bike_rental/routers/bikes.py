"""Browsing the catalogue and checking availability for a pickup date."""

from fastapi import APIRouter

router = APIRouter(prefix="/bikes", tags=["bikes"])
