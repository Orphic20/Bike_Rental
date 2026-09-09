# Muñoz Bike Rental

A bike rental system for the shop in Bagong Sikat, Science City of Muñoz.

- **Backend** — FastAPI + SQLModel against Supabase Postgres (`src/bike_rental`)
- **Frontend** — React 19 + Vite + Tailwind v4 (`Frontend/`)
- **Auth** — Supabase; the browser holds the session, the API verifies the JWT

See [ARCHITECTURE.md](ARCHITECTURE.md) for the product rules and data model, and
[DESIGN.md](DESIGN.md) for the visual system.

## Requirements

- Python 3.14+ with [uv](https://docs.astral.sh/uv/)
- Node 20+ with pnpm (`corepack pnpm …` works without a global install)
- A Supabase project

## Backend

Create `.env` in the repo root:

```ini
DATABASE_URL=postgresql://…        # Supabase connection string
SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
CORS_ORIGINS=http://localhost:3000  # comma-separated
```

Then:

```bash
uv sync
uv run python dev.py     # http://localhost:8000, docs at /docs
```

`SUPABASE_JWKS_URL` matters: new Supabase projects sign tokens with ES256, whose
public key lives in JWKS. The `SUPABASE_JWT_SECRET` from the dashboard is HS256
only and will not verify these tokens.

## Frontend

```bash
cd Frontend
cp .env.example .env     # then fill in the Supabase values
corepack pnpm install
corepack pnpm run dev    # http://localhost:3000
```

The dev server pins port 3000 because that is the default entry in the backend's
`CORS_ORIGINS`. If you change one, change the other.

Without `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` the app still runs: the
landing page and catalogue are public. Sign-in and booking stay disabled and the
UI says so.

### Scripts

| Command | Purpose |
|---|---|
| `pnpm dev` | Vite dev server on port 3000 |
| `pnpm build` | Client bundle to `dist/public`, Express server to `dist/` |
| `pnpm start` | Serve the production build |
| `pnpm check` | `tsc --noEmit` |
| `pnpm format` | Prettier |

## API

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /health` | Liveness; does not touch the database | none |
| `GET /bikes` | Catalogue; `type`, `pickup_date`, and `rate` filter availability | none |
| `GET /users/me` | Caller's profile and role | bearer |
| `POST /bookings` | Create a group booking, one rental row per bike | bearer |
| `GET /bookings` | Bookings the caller owns, newest first | bearer |
| `GET /bookings/{id}` | A single owned booking | bearer |

Money is `numeric(10,2)` in Postgres and serialises as a **string** in JSON, so
parse before doing arithmetic. The frontend uses `toAmount` in `lib/format.ts`.

`GET /bikes?pickup_date=…` derives each bike's occupied window from its rentals
and marks overlaps unavailable, using the same helpers `POST /bookings` uses to
reject conflicts. Keeping both on `availability.py` is what stops the catalogue
from advertising a bike the booking endpoint would refuse with a 409.

## Not built yet

The `payments`, `staff`, `admin`, and `extensions_swaps` routers are registered
but expose no endpoints. Consequently:

- The Staff and Admin screens run on sample data and are labelled as such. Admin
  inventory counts are the exception; they come from `GET /bikes`.
- "Extend rent" and "Request a swap" tell the customer the feature is pending.
- GCash proof is submitted as a receipt **link** plus reference number. Direct
  file upload needs an endpoint (Cloudinary is already a backend dependency).
- Staff cannot record payment or release a bike, so bookings stay `reserved`.
