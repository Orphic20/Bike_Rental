# Muñoz Bike Rental

A bike rental system for the shop in Bagong Sikat, Science City of Muñoz.

- **Backend** — FastAPI + SQLModel against Supabase Postgres (`src/bike_rental`)
- **Frontend** — React 19 + Vite + Tailwind v4 (`Frontend/`)
- **Auth** — Supabase; the browser holds the session, the API verifies the JWT
- **Photos** — Cloudinary (`munoz/bikes`, `munoz/receipts`)

See [ARCHITECTURE.md](ARCHITECTURE.md) for the product rules and data model, and
[DESIGN.md](DESIGN.md) for the visual system.

Customers browse Japanese, Folding, and Mountain bikes, add them to a group
booking, and pay the exact total by cash at the counter or GCash. The online
catalogue is only part of the fleet: if those bikes are fully booked, walk-ins
can still rent extra bikes at the counter.

Staff run the counter from **Today's queue**, **Reservations**, **Swap
requests**, and **Extension requests**. Admin manages inventory photos, users,
shop hours, closures, revenue, and audit history.

## Requirements

- Python 3.14+ with [uv](https://docs.astral.sh/uv/)
- Node 20+ with pnpm (`corepack pnpm …` works without a global install)
- A Supabase project
- A Cloudinary account (bike photos and GCash receipts)

## Backend

Create `.env` in the repo root (see `.env.example`):

```ini
DATABASE_URL=postgresql://…        # Supabase connection string
SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
CORS_ORIGINS=http://localhost:3000  # comma-separated
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CRON_SECRET=replace-with-a-long-random-value
```

Then:

```bash
uv sync
uv run python dev.py     # http://localhost:8000, docs at /docs
uv run pytest            # lifecycle, extensions, uploads, staff helpers
```

Apply every file in `supabase/migrations/` on the Supabase project before
pointing the API at it.

`SUPABASE_JWKS_URL` matters: new Supabase projects sign tokens with ES256, whose
public key lives in JWKS. The `SUPABASE_JWT_SECRET` from the dashboard is HS256
only and will not verify these tokens.

## Frontend

```bash
cd Frontend
cp .env.example .env     # then fill in the API and Supabase values
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

## Staff desk

Today's queue lists today's pickups in this order: cash (or GCash still needing
a decision), ready to release, out on rent, cancelled, returned. Within a
status, rows stay ordered by pickup date and estimated time.

- **Reservations** shows cash-at-counter bookings that have not been released.
- Staff record exact cash, verify GCash, release bikes, reject a reservation, or
  return a rental.
- A daily rental released after 7:00 PM Asia/Manila is due at 7:00 PM the next
  day. Postgres cannot store a return time before the release time.

Customers can cancel an unreleased reservation they own. Staff can reject one
from the desk. Both put reserved rentals back to cancelled.

## API

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /health` | Liveness; does not touch the database | none |
| `GET /shop/settings` | Open/closed flag | none |
| `GET /shop/closures` | Public closure windows | none |
| `GET /bikes` | Catalogue; `type`, `pickup_date`, and `rate` filter availability | none |
| `GET /users/me` | Caller's profile and role | bearer |
| `POST /bookings` | Create a group booking, one rental row per bike | bearer |
| `GET /bookings` | Bookings the caller owns, newest first | bearer |
| `GET /bookings/{id}` | A single owned booking | bearer |
| `POST /bookings/{id}/cancel` | Owner or staff cancel an unreleased reservation | bearer |
| `POST /payments/{id}/cash` | Record exact cash at the counter | staff/admin bearer |
| `POST /uploads/receipt` | GCash receipt to Cloudinary | bearer |
| `POST /uploads/bike` | Bike photo to Cloudinary | staff/admin bearer |
| `GET /staff/bookings` | Counter queue; search and tab filters | staff/admin bearer |
| `POST /staff/bookings/{id}/release` | Paid reserved booking → active / rented | staff/admin bearer |
| `POST /staff/bookings/{id}/reject` | Reject an unreleased reservation | staff/admin bearer |
| `POST /staff/rentals/{id}/return` | Record a return | staff/admin bearer |
| `GET /staff/payments/pending` | GCash receipts waiting on staff | staff/admin bearer |
| `POST /staff/payments/{id}/verify` | Accept or reject a GCash receipt | staff/admin bearer |
| `POST /rentals/{id}/extensions` | Price and request one paid extension | customer bearer |
| `POST /staff/extensions/{booking_id}/approve` | Apply a fully paid extension and update `due_at` | staff/admin bearer |
| `POST /rentals/{id}/swap-requests` | Request a replacement for an active rental | customer bearer |
| `GET /staff/swap-requests` | Swap-request history, newest first | staff/admin bearer |
| `POST /staff/swap-requests/{id}/decide` | Approve with a replacement bike or reject | staff/admin bearer |
| `GET /admin/bikes` | Full fleet including retired | admin bearer |
| `POST /admin/bikes` | Add a bike | admin bearer |
| `PATCH /admin/bikes/{id}` | Edit a bike, including photo URL | admin bearer |
| `GET /admin/reports/revenue` | Paid revenue totals split by payment method and rate | admin bearer |
| `GET /admin/audit-logs?page=1&page_size=25` | Paginated audit history, newest first | admin bearer |
| `PUT /admin/shop/settings` | Open or panic-close the shop | admin bearer |
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
`.github/workflows/lifecycle-sweep.yml` wakes `GET /health`, then calls the API
once to:

- mark unreleased eligible reservations as `no_show`;
- mark past-due `active` rentals as `overdue`;
- keep paid no-shows paid and skip GCash bookings pending verification;
- delete GCash receipt images and reference numbers older than 1 month;
- write `rental.no_show`, `rental.overdue`, and `booking.receipt_purged` audit entries; and
- delete audit log rows older than 6 months.

The workflow does not retry a hung POST. Apply the Supabase migrations before
enabling it. Then configure:

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
