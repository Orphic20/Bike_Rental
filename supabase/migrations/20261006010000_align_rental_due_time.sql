-- Rental periods end when the shop closes: 7:00 PM Asia/Manila (11:00 UTC).
-- Normalize active rows created by the old 23:59:59 UTC release calculation.

update public.rentals
set due_at = date_trunc('day', due_at) + interval '11 hours',
    updated_at = now()
where status = 'active'
  and due_at is not null
  and due_at::time >= time '23:59:58';
