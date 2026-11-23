-- Keep the database queue allowlist aligned with the agent's fixed read-only task map.
-- These audit tasks inspect EngineerMode source, radio state, and capabilities only.
alter table private.relay_commands
  drop constraint if exists relay_commands_task_check;

alter table private.relay_commands
  add constraint relay_commands_task_check
  check (task in (
    'inventory',
    'telephony',
    'radio',
    'source',
    'connectivity',
    'engineermode_audit',
    'worldmode_audit',
    'band_audit',
    'ril_audit',
    'network_audit',
    'component_audit',
    'safety_audit'
  ));

-- A command that was claimed but never completed must not remain stuck forever.
-- Collection is bounded to 25 seconds, while queue commands expire after two minutes.
create or replace function public.relay_claim_command(p_device_id uuid)
returns table(command_id uuid, task text, expires_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
begin
  update private.relay_commands as expired_command
    set status = 'expired'
    where expired_command.device_id = p_device_id
      and expired_command.status in ('pending', 'claimed')
      and expired_command.expires_at <= now();

  update private.relay_devices as device
    set last_seen_at = now()
    where device.id = p_device_id
      and device.status = 'active';

  return query
  with candidate as (
    select c.id
    from private.relay_commands as c
    where c.device_id = p_device_id
      and c.status = 'pending'
      and c.expires_at > now()
    order by c.created_at
    for update skip locked
    limit 1
  )
  update private.relay_commands as claimed_command
    set status = 'claimed', claimed_at = now()
    from candidate
    where claimed_command.id = candidate.id
    returning claimed_command.id, claimed_command.task, claimed_command.expires_at;
end;
$$;
