-- Reserved rentals have released_at and due_at both null, and Postgres reads
-- tstzrange(null, null) as (,) — the range covering all of time. That made every
-- reservation collide with every other rental for the same bike, so a bike could
-- only ever hold one unreturned rental regardless of dates.
--
-- Restrict the constraint to rentals that have actually been released, where the
-- range is real. It now guarantees the physically impossible case: one bike out
-- with two customers at once. Availability for a future pickup date is computed
-- from rentals in the API, which is where it has to live — a reservation records
-- only expected_pickup_date, so there is no end bound to compare against.

alter table public.rentals
    drop constraint if exists no_overlapping_active_rentals;

alter table public.rentals
    add constraint no_overlapping_active_rentals
    exclude using gist (bike_id with =, tstzrange(released_at, due_at) with &&)
    where (returned_at is null and released_at is not null);
