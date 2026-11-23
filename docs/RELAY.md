# Relay deployment notes

The Edge Function disables gateway JWT verification because it authenticates each device using a high-entropy bearer token whose SHA-256 hash is stored in the private database. The function itself must be deployed with its custom authentication code intact.

Required platform-provided server secrets:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

These values must remain in the Edge Function runtime. Never copy them into Termux, GitHub, or the Android app.

The SQL migration creates private tables and narrowly scoped SECURITY DEFINER RPC functions. Public, anon, and authenticated roles are denied execution. The Edge Function uses the service role only to call those RPCs; no client-side table access is needed.

ChatGPT queues commands through its authenticated Supabase database connector, inserting only a task from the SQL CHECK allowlist. The phone polls over outbound HTTPS; no inbound phone port or public Termux server is required.

## First device enrollment

The local agent creates a random bearer token and stores it only on the phone. It prints the device UUID and SHA-256 hash, never the token. Register that pair in `private.relay_devices` using the trusted database connector. Do not paste the local relay.json file into chat or GitHub.

## Queueing a task

Only use these exact fixed read-only tasks:
- `inventory`
- `telephony`
- `radio`
- `source`
- `connectivity`
- `engineermode_audit`
- `worldmode_audit`
- `band_audit`
- `ril_audit`
- `network_audit`
- `component_audit`
- `safety_audit`

Use a maximum two-minute expiry. Never enqueue shell text, SQL, arbitrary arguments, or modem-write operations. The local agent independently checks the task against its fixed allowlist.

Commands claimed by a device but not completed before expiry are marked expired on the next poll, so stale claims cannot remain stuck indefinitely.
