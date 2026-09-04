"""Extending a rental and swapping the bike on an active one.

No prefix: these cover two separate resources, /extensions and /swaps.
"""

from fastapi import APIRouter

router = APIRouter(tags=["extensions & swaps"])
