-- Phase 5: track applied extensions and preserve the bike a swap started with.

alter table public.bookings
  add column if not exists extension_applied_at timestamptz;

alter table public.swap_requests
  add column if not exists old_bike_id uuid;

update public.swap_requests as request
set old_bike_id = rental.bike_id
from public.rentals as rental
where rental.id = request.rental_id
  and request.old_bike_id is null;

alter table public.swap_requests
  alter column old_bike_id set not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'swap_requests_old_bike_id_fkey'
      and conrelid = 'public.swap_requests'::regclass
  ) then
    alter table public.swap_requests
      add constraint swap_requests_old_bike_id_fkey
      foreign key (old_bike_id) references public.bikes (id);
  end if;
end
$$;

create unique index if not exists one_pending_extension_per_rental_idx
  on public.bookings (rental_id)
  where booking_type = 'extension'
    and extension_applied_at is null
    and payment_status not in ('cancelled', 'rejected');

create unique index if not exists one_pending_swap_per_rental_idx
  on public.swap_requests (rental_id)
  where status = 'pending';

create index if not exists swap_requests_created_at_idx
  on public.swap_requests (created_at desc);
