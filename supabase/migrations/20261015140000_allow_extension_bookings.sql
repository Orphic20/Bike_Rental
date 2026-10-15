-- Extension bookings insert booking_type = 'extension'. A leftover CHECK that
-- only allows 'new' 500s POST /rentals/{id}/extensions (the browser then shows
-- "Cannot reach the API"). Also let extensions copy waiver from the parent
-- without failing if an older booking row has none.

do $$
declare
  constraint_name text;
begin
  for constraint_name in
    select con.conname
    from pg_constraint con
    join pg_class rel on rel.oid = con.conrelid
    join pg_namespace nsp on nsp.oid = rel.relnamespace
    where nsp.nspname = 'public'
      and rel.relname = 'bookings'
      and con.contype = 'c'
      and pg_get_constraintdef(con.oid) ~* 'booking_type'
  loop
    execute format(
      'alter table public.bookings drop constraint %I',
      constraint_name
    );
  end loop;
end
$$;

alter table public.bookings
  add constraint bookings_booking_type_check
  check (booking_type in ('new', 'extension'));

alter table public.bookings
  alter column waiver_version drop not null;
