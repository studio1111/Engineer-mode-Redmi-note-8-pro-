# Redmi Engineer Lab

Read-only-first diagnostics and an authenticated command-polling agent for Xiaomi Redmi Note 8 Pro (begonia / MediaTek MTK6785), designed for Termux + Shizuku Rish.

## Current implementation

- Fixed task allowlist: inventory, telephony, radio, connectivity, broad source audit, and six focused read-only EngineerMode audits (World Mode, band selection, RIL/AT, network capabilities, component inventory, safety/persistence).
- No arbitrary shell command API.
- No modem, RF, NVRAM/NVDATA, calibration, IMEI, band, or WorldMode writes.
- Subscriber identifiers are redacted before local report persistence and relay upload.
- Optional authenticated relay uses per-device random bearer credentials, SHA-256 token verification, short-lived queue items, one-time claiming, and completion binding to the enrolled device.
- Relay tables live in a non-exposed `private` schema; only server-side service role can invoke narrowly scoped RPC functions.
- Local bearer token is generated and stored on the phone with restrictive file permissions; only device UUID and token hash are shared for enrollment.

## Security warning

This repository is currently public. Make it private before adding operational details or any deployment secrets. Never commit local relay credentials, Supabase secret/service-role keys, raw radio logs, or unredacted device reports.

## One-time Termux setup

Run this single command in Termux:

```sh
pkg install -y curl && bash -c "$(curl -fsSL https://raw.githubusercontent.com/studio1111/Engineer-mode-Redmi-note-8-pro-/main/bootstrap-termux.sh)"
```

The script installs Git/Python, clones or fast-forward-updates the repository, compiles the agent, runs unit tests, checks Rish access, and creates local relay credentials once. It does not change modem settings.

The script prints an enrollment JSON containing `device_id` and `token_sha256`. Send that JSON to the assistant for registration. The actual bearer token remains in:

```
~/.config/redmi-engineer-lab/relay.json
```

Do not share that file or its `token` value.

## Local diagnostics

```sh
cd ~/RedmiEngineerLab
python agent.py --task inventory
python agent.py --task telephony
python agent.py --task radio
python agent.py --task connectivity
python agent.py --task source
python agent.py --task worldmode_audit
python agent.py --task band_audit
python agent.py --task ril_audit
python agent.py --task network_audit
python agent.py --task component_audit
python agent.py --task safety_audit
python -m unittest discover -s tests -v
```

Reports are stored under `reports/` with restrictive file permissions. Schema v2 reports include `output_length` and an explicit `truncated` flag; `status=ok` does not mean the report was complete. Review them before sharing.

## Relay architecture

1. ChatGPT queues an allowlisted task in the private database using its authenticated Supabase connector.
2. The Termux agent polls the Edge Function over outbound HTTPS.
3. The Edge Function verifies the device token hash and claims at most one unexpired task.
4. The agent validates the task again against its local allowlist, executes only the matching fixed collector, redacts the result, and submits the report.
5. The Edge Function accepts completion only for the same enrolled device and a currently claimed, unexpired command.

The Edge Function requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` as server-side environment variables. Never place these in Termux or GitHub.

## Start and stop the relay

After the backend is deployed and the device is enrolled:

```sh
cd ~/RedmiEngineerLab
bash start-relay.sh https://PROJECT_REF.supabase.co/functions/v1/device-relay
```

Stop it with:

```sh
bash stop-relay.sh
```

The relay now runs under `relay-supervisor.sh`, which automatically restarts the worker after an unexpected exit with bounded backoff (5–60 seconds). The URL is stored locally with mode 0600.\n\nFor automatic startup after a device reboot, install and open the official **Termux:Boot** add-on once, then run:\n\n```sh\ncd ~/RedmiEngineerLab\nbash install-termux-boot.sh\n```\n\nThis installs `~/.termux/boot/start-redmi-engineer-lab`, which waits for Android networking and starts the saved relay URL. Android battery management can still suspend or kill Termux; set Termux battery usage to Unrestricted if Android offers that setting. The scripts do not alter system power settings or grant Shizuku permissions.

## Backend deployment

After a Supabase project is selected and ready:

1. Apply all SQL migrations in `supabase/migrations/` in filename order, including `202611240001_read_only_audit_tasks_and_expiry.sql`.
2. Deploy `supabase/functions/device-relay/index.ts` as `device-relay` with JWT verification disabled because the function performs its own per-device bearer-token authentication.
3. Verify the database functions and Edge Function logs.
4. Register the device using only the enrollment UUID and SHA-256 hash.
5. Queue a harmless `inventory` task and verify the complete round trip.

## Safety boundaries

- The relay accepts only named read-only tasks; it never accepts shell text or arbitrary arguments.
- Commands expire after two minutes and cannot be claimed twice.
- The server stores only the token hash; the phone stores the bearer token.
- WorldMode, band selection, RF, NVRAM/NVDATA, calibration, and identity changes remain approval-gated and are not implemented in the agent.
- A green CI run proves code-level checks only; it does not establish safe modem behavior or a working physical-device connection.
