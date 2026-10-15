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
CRON_SECRET=replace-with-a-long-random-value
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
| `POST /rentals/{id}/extensions` | Price and request one paid extension for an active rental | customer bearer |
| `POST /staff/extensions/{booking_id}/approve` | Apply a fully paid extension and update `due_at` | staff/admin bearer |
| `POST /rentals/{id}/swap-requests` | Request a replacement for an active rental | customer bearer |
| `GET /staff/swap-requests` | Swap-request history, newest first | staff/admin bearer |
| `POST /staff/swap-requests/{id}/decide` | Approve with a replacement bike or reject | staff/admin bearer |
| `GET /admin/reports/revenue` | Paid revenue totals split by payment method and rate | admin bearer |
| `GET /admin/audit-logs?page=1&page_size=25` | Paginated audit history, newest first | admin bearer |
| `POST /admin/jobs/lifecycle-sweep?dry_run=true` | Preview or run the lifecycle sweep | admin bearer |
| `POST /internal/jobs/lifecycle-sweep` | Scheduled no-show and overdue sweep | `X-Cron-Secret` |

Money is `numeric(10,2)` in Postgres and serialises as a **string** in JSON, so
parse before doing arithmetic. The frontend uses `toAmount` in `lib/format.ts`.

`GET /bikes?pickup_date=…` derives each bike's occupied window from its rentals
and marks overlaps unavailable, using the same helpers `POST /bookings` uses to
reject conflicts. Keeping both on `availability.py` is what stops the catalogue
from advertising a bike the booking endpoint would refuse with a 409.

## Lifecycle automation

Rentals are due at 7:00 PM Asia/Manila on their final rental day. At 7:05 PM,
`.github/workflows/lifecycle-sweep.yml` calls the API to:

- mark unreleased eligible reservations as `no_show`;
- mark past-due `active` rentals as `overdue`;
- keep paid no-shows paid and skip GCash bookings pending verification;
- delete GCash receipt images older than 30 days (reference numbers stay); and
- write `rental.no_show`, `rental.overdue`, and `booking.receipt_purged` audit entries.

Apply the Supabase migrations before enabling the workflow. Then configure:

1. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Add it to Render as `CRON_SECRET`.
3. In GitHub repository **Settings → Secrets and variables → Actions**, add:
   - `AUTOMATION_URL`: the Render API origin, without a trailing slash.
   - `AUTOMATION_SECRET`: the same value as Render's `CRON_SECRET`.
4. Open **Actions → Rental lifecycle sweep → Run workflow** once and confirm it
   succeeds. Scheduled runs use `5 11 * * *` (7:05 PM Asia/Manila).

The admin endpoint defaults to `dry_run=true`. Pass `dry_run=false` only when
you intend to apply the transitions.

## Extensions and swaps

An extension is one new booking linked to one existing rental. Creating it
checks the bike's next daily or weekly window and calculates the exact price.
The existing cash/GCash endpoints settle the extension. Only
`POST /staff/extensions/{booking_id}/approve` applies a paid extension to the
rental's `due_at`, with availability checked again while rows are locked.

Customers can request one pending swap per active rental. Staff chooses an
available replacement or rejects it. Approval locks both bikes, checks
reservation conflicts through the current due date, changes the rental's bike,
and records an audit event.

Apply `supabase/migrations/20261015010000_extensions_and_swaps.sql` before
deploying this version.
