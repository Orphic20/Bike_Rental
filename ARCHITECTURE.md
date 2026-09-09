# Muñoz Bike Rental Architecture — Final Specification

## 1. Product Rules

Muñoz Bike Rental rents three bike types: **Japanese**, **Folding**, and **Mountain**. Customers can browse the fleet, choose multiple bikes for one group booking, select a daily or weekly rate, and choose cash or GCash.

Future reservations require a **pickup date only**. The return date is not entered during reservation. The rental due time is established when Staff releases the bike or records the rental duration.

The system does not collect mobile numbers, hold IDs as collateral, or require formal return-inspection records. Staff may visually verify the customer’s name against the physical ID presented at pickup, but the application does not store the ID or track its custody.

Every booking requires **one exact full payment**. Cash must equal the exact total, with no change and no partial payment. GCash must equal the exact total and include receipt proof plus a reference number. The system does not support credit, unpaid tabs, carried balances, or installment payments.

## 2. Customer Flow

Customers sign in and maintain a profile containing their authenticated user ID, email, full government name, role, and timestamps. A mobile number is not required. If legal acceptance is required, store the accepted Terms and waiver version with its timestamp.

The landing page opens separate inventory pages for Japanese, Folding, and Mountain bikes. Each inventory page contains individual bikes and an **Add to Group Booking** action. A sticky booking summary shows selected bikes, pickup context, rate, and exact total.

When the first bike is selected, the customer chooses either **Book today** or **Reserve for later**. Reserve for later requests only a pickup date. The customer then reviews the bikes, selects Daily or Weekly, confirms their name and email, accepts the waiver and Terms, chooses Cash or GCash, and submits the booking.

For GCash, the customer sees the store’s QR code or payment instructions, uploads a receipt, enters the reference number, and submits proof for verification. The receipt and reference number are required, and the payment amount must equal the exact booking total.

For cash, the customer receives a reservation confirmation stating that the exact total must be paid at pickup. The bikes are not released until Staff records the exact cash payment.

My Rides groups all rentals under the reservation reference. It shows each bike, pickup date, rate, payment status, and reservation status. It does not display a partial balance because partial payment is not supported.

## 3. Staff Flow

Staff views expected pickups, expected returns, GCash verification requests, swap requests, and current shop status.

### Pickup

1. Staff searches by reservation reference or customer name.
2. Staff confirms the customer’s full government name against the physical ID presented at the counter.
3. For cash, Staff receives and records the exact total. Staff must not accept a partial amount or provide change.
4. For GCash, Staff reviews the receipt and reference number and verifies that the exact total arrived in the store’s GCash account.
5. Staff releases the bikes only after the booking is fully paid.
6. Each rental changes from `reserved` to `active`, and each bike changes from `available` to `rented`.

The application does not store the physical ID, record ID collateral, or require an ID-return step.

### Return

Staff records the actual return time and marks the rental returned. If a late fee applies, it must be paid in full through a separate exact cash or GCash payment before the rental is completed. No amount is added to a customer tab. The bike becomes `available`, or Staff may place it in `maintenance` if a separate maintenance issue is identified.

A formal inspection table is not required. An optional `damage_reports` table may be added later if the business needs to record damage separately.

### Extension

An extension is a **new booking**, not a separate extension table. The system checks availability, calculates the additional daily or weekly price, creates an extension booking, links it to the original booking with `parent_booking_id`, and links it to the affected rental with `rental_id`.

The exact extension amount must be paid before activation. A cash extension requires exact full cash payment; a GCash extension requires exact full GCash payment with receipt and reference verification. Only after payment and Staff approval is the rental’s `due_at` updated. No extension amount remains unpaid or is carried forward.

If multiple bikes are extended, create one extension booking per affected rental, all using the same `parent_booking_id`. This preserves the no-junction-table design while allowing each bike to be extended independently.

### Swap

Customers may request a swap for a specific active rental. Staff approves or rejects the request based on inventory. When approved, the replacement bike is assigned to that rental and the original bike returns to `available` or `maintenance` according to the Staff decision.

## 4. Admin Flow

Admin manages bikes, bike types, bookings, users, payments, shop status, and audit history.

| Area | Responsibilities |
|---|---|
| Bikes | Create, edit, archive, retire, and update bike status. |
| Bookings | View, approve, cancel, and override reservations. |
| Users | View users, change roles, suspend accounts, and restore accounts. |
| Payments | Review GCash proof, verify payments, record exact cash payments, and process refunds where permitted. |
| Financial reporting | Report exact paid revenue by cash or GCash and by Daily or Weekly rate. |
| Inventory | View available, rented, maintenance, and retired bikes, plus rental reservations. |
| Shop controls | Open or close the shop and log the Admin who changed the setting. |
| Audit history | Record payment verification, cancellation, release, extension, swap, and shop-status changes. |

## 5. Status Lifecycle

The bike’s inventory status is separate from the rental status.

| Bike status | Meaning |
|---|---|
| `available` | Can be selected or released. |
| `rented` | Currently assigned to an active rental. |
| `maintenance` | Temporarily unavailable. |
| `retired` | Permanently removed from service. |

| Rental status | Meaning |
|---|---|
| `reserved` | Assigned to a booking but not yet released. |
| `active` | Released to the customer. |
| `overdue` | Due time passed without a recorded return. |
| `returned` | Staff recorded the return. |
| `cancelled` | Cancelled before release. |
| `no_show` | Pickup deadline passed without release. |

Do not set a bike’s inventory status to `reserved`; determine reservation conflicts from rentals and their date or pickup records.

## 6. Booking Model

One original group booking may contain many rental rows. Every selected bike receives one row in `rentals`, and those rows share one `booking_id`.

An extension is linked as follows:

```text
Original booking VC-1001
 ├── Rental A: Japanese bike
 └── Rental B: Folding bike

Extension booking VC-1002
 ├── booking_type: extension
 ├── parent_booking_id: VC-1001
 ├── rental_id: Rental A
 └── exact payment: completed
```

Recommended booking fields are `id`, `user_id`, `expected_pickup_date`, `rate_selected`, `total_price`, `amount_paid`, `payment_method`, `payment_status`, `booking_type`, `parent_booking_id`, optional `rental_id`, waiver version and timestamp, status, and timestamps.

For the exact-payment rule, `amount_paid` may be `0` before payment or exactly `total_price` after payment. It must never be between those values or greater than `total_price`.

## 7. Table Assessment

The following tables are appropriate:

| Table | Purpose |
|---|---|
| `roles` | Customer, Staff, and Admin roles. |
| `users` | Authenticated profile and legal-acceptance metadata. |
| `bikes` | Individual bike inventory and rates. |
| `bookings` | Group reservation, extension relationship, price, and payment state. |
| `rentals` | One selected bike per row and its rental lifecycle. |
| `swap_requests` | Replacement-bike requests for active rentals. |
| `shop_settings` | Current open or closed state. |
| `shop_status_logs` | Historical shop-status changes. |
| `audit_logs` | Important Staff and Admin actions. |
| `late_fees` | Optional; use only if late fees are part of the final policy. |
| `damage_reports` | Optional; use only if Staff must record damage. |

Do not create `id_collaterals`, `return_inspections`, `rental_extensions`, or `booking_items` for this design. One rental row per selected bike already handles multi-bike bookings.

A separate `payments` table is optional for the current flow. Keeping payment columns on `bookings` is acceptable when each booking has exactly one full payment. Add a payments table later if you need multiple payment attempts, refunds, resubmissions, or detailed payment history.

## 8. Important Constraints

Create `bookings` and `rentals` before adding their circular foreign keys. `rentals.booking_id` references `bookings.id`, while an extension’s `bookings.rental_id` references `rentals.id`; add these constraints afterward with `ALTER TABLE`.

Remove any stored `balance_due` column or calculate it only as `total_price - amount_paid`. Add checks equivalent to:

```sql
CHECK (amount_paid >= 0 AND amount_paid <= total_price)
```

For GCash, require a non-empty receipt URL and reference number. For cash, require the payment status to remain unpaid until Staff records the exact total. A booking becomes eligible for release only when `amount_paid = total_price`.

Use `numeric(10,2)` for all rates, prices, payments, refunds, and late fees. Add indexes on booking ownership, pickup date, booking status, parent booking, rental booking, bike, and payment status. Use transactions and a database-level conflict rule to prevent overlapping rentals for the same bike.

## 9. Automation

A scheduled no-show process may cancel reservations that pass the configured pickup deadline without release and return their bikes to `available`. Because the user enters only a pickup date, the deadline must use a configured pickup time or shop-opening rule.

An overdue process may mark active rentals as `overdue` after `due_at` passes. If late fees are enabled, calculate them according to the configured policy, require exact payment, and avoid charging the same period twice.

## 10. Implementation Status

The HTTP surface currently implemented by the FastAPI service in `src/bike_rental`:

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /health` | Liveness probe; deliberately does not touch the database. | none |
| `GET /bikes` | Catalogue, optionally filtered by `type` and marked for availability against a `pickup_date` + `rate`. | none |
| `GET /users/me` | Caller's profile and role. | bearer |
| `POST /bookings` | Create a group booking with one rental row per bike. | bearer |
| `GET /bookings` | Every booking the caller owns, newest first. | bearer |
| `GET /bookings/{booking_id}` | A single owned booking. | bearer |

The `payments`, `staff`, `admin`, and `extensions_swaps` routers are registered but expose no endpoints yet. The Staff and Admin screens in the frontend remain unconnected prototypes until those land.

Authentication is delegated to Supabase. The frontend obtains a session through `@supabase/supabase-js` and sends the access token as a bearer token; the backend verifies it against the project's JWKS endpoint using ES256.
