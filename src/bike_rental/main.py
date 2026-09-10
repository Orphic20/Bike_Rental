import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bike_rental.routers import (
    admin,
    bikes,
    bookings,
    extensions_swaps,
    payments,
    staff,
    uploads,
    users,
)

load_dotenv()

app = FastAPI(
    title="Munoz Bike Rental API",
    version="0.1.0",
)

# The frontend is served from Cloudflare Pages, a different origin, so browsers
# need these headers. Set CORS_ORIGINS in production as a comma-separated list.
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    # Auth travels as a bearer token in the Authorization header, not a cookie,
    # so the browser never needs to send credentials cross-origin.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (users, bikes, bookings, payments, staff, uploads, extensions_swaps, admin):
    app.include_router(module.router)

@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness only — deliberately does not touch the database.

    UptimeRobot pings this every few minutes to stop Render's free tier from
    idling, so it needs to stay cheap and not burn a Supabase connection.
    """
    return {"status": "ok"}
