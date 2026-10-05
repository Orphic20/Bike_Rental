-- Scheduled shop closures. shop_settings.is_open stays the panic toggle.
-- schedule_override_until lets admin "open anyway" through a hours window.
-- Buffers are applied in the API (effective start/end), not generated columns.

alter table public.shop_settings
  add column if not exists schedule_override_until timestamptz;

create table if not exists public.shop_closures (
  id uuid primary key default gen_random_uuid(),
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  kind text not null,
  buffer_before_min integer not null default 0,
  buffer_after_min integer not null default 0,
  message text,
  created_by_admin_id uuid references public.users (id),
  created_at timestamptz not null default now(),
  constraint shop_closures_kind_check
    check (kind in ('hours', 'full_day')),
  constraint shop_closures_buffer_before_check
    check (buffer_before_min in (0, 30, 60)),
  constraint shop_closures_buffer_after_check
    check (buffer_after_min in (0, 30, 60)),
  constraint shop_closures_range_check
    check (starts_at < ends_at)
);

create index if not exists shop_closures_range_idx
  on public.shop_closures (starts_at, ends_at);

alter table public.shop_closures enable row level security;
