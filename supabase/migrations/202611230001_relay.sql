-- Private command relay. No client role can access these tables or RPCs.
create schema if not exists private;

create table if not exists private.relay_devices (
  id uuid primary key,
  token_sha256 text not null check (token_sha256 ~ '^[0-9a-f]{64}$'),
  label text not null default 'Redmi Note 8 Pro',
  status text not null default 'active' check (status in ('active','revoked')),
  created_at timestamptz not null default now(),
  last_seen_at timestamptz
);

create table if not exists private.relay_commands (
  id uuid primary key default gen_random_uuid(),
  device_id uuid not null references private.relay_devices(id) on delete cascade,
  task text not null check (task in ('inventory','telephony','radio','source','connectivity')),
  status text not null default 'pending' check (status in ('pending','claimed','completed','expired')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '2 minutes'),
  claimed_at timestamptz,
  completed_at timestamptz,
  result jsonb,
  check (expires_at > created_at)
);

create index if not exists relay_commands_pending_idx
  on private.relay_commands (device_id, created_at)
  where status = 'pending';

alter table private.relay_devices enable row level security;
alter table private.relay_commands enable row level security;
revoke all on schema private from public, anon, authenticated;
revoke all on all tables in schema private from public, anon, authenticated, service_role;
grant usage on schema private to service_role;
grant select, insert, update, delete on all tables in schema private to service_role;

create or replace function public.relay_auth_device(p_device_id uuid, p_token_sha256 text)
returns boolean
language sql
security definer
set search_path = ''
as $$
  select exists (
    select 1 from private.relay_devices d
    where d.id = p_device_id
      and d.token_sha256 = p_token_sha256
      and d.status = 'active'
  );
$$;

create or replace function public.relay_claim_command(p_device_id uuid)
returns table(command_id uuid, task text, expires_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
begin
  update private.relay_devices
    set last_seen_at = now()
    where id = p_device_id and status = 'active';

  return query
  with candidate as (
    select c.id
    from private.relay_commands c
    where c.device_id = p_device_id
      and c.status = 'pending'
      and c.expires_at > now()
    order by c.created_at
    for update skip locked
    limit 1
  )
  update private.relay_commands c
    set status = 'claimed', claimed_at = now()
    from candidate
    where c.id = candidate.id
    returning c.id, c.task, c.expires_at;
end;
$$;

create or replace function public.relay_complete_command(
  p_device_id uuid,
  p_command_id uuid,
  p_status text,
  p_result jsonb
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  changed integer;
begin
  if p_status not in ('ok','error','timeout','unavailable') then
    return false;
  end if;
  if pg_column_size(p_result) > 65536 then
    return false;
  end if;

  update private.relay_commands
    set status = 'completed',
        completed_at = now(),
        result = p_result
    where id = p_command_id
      and device_id = p_device_id
      and status = 'claimed'
      and expires_at > now();

  get diagnostics changed = row_count;
  return changed = 1;
end;
$$;

revoke all on function public.relay_auth_device(uuid,text) from public, anon, authenticated;
revoke all on function public.relay_claim_command(uuid) from public, anon, authenticated;
revoke all on function public.relay_complete_command(uuid,uuid,text,jsonb) from public, anon, authenticated;
grant execute on function public.relay_auth_device(uuid,text) to service_role;
grant execute on function public.relay_claim_command(uuid) to service_role;
grant execute on function public.relay_complete_command(uuid,uuid,text,jsonb) to service_role;
