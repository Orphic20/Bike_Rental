-- Estimated counter pickup time within shop hours (8:00 AM–7:00 PM Asia/Manila).

alter table public.bookings
  add column if not exists expected_pickup_time time;

alter table public.bookings
  drop constraint if exists bookings_expected_pickup_time_hours;

alter table public.bookings
  add constraint bookings_expected_pickup_time_hours
  check (
    expected_pickup_time is null
    or (
      expected_pickup_time >= time '08:00'
      and expected_pickup_time <= time '19:00'
    )
  );
