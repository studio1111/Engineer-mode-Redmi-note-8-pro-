# Security Policy

## Scope

This project collects diagnostic information from an Android device and relays a strict allowlist of read-only tasks. Radio logs, telephony state, and decoded source files may contain sensitive information.

## Rules

- Never commit IMEI, IMSI, ICCID, phone numbers, SIM identifiers, authentication tokens, relay secrets, or raw unredacted device dumps.
- The repository is currently public; make it private before adding any operational details. No secrets belong in GitHub regardless of visibility.
- Never share `~/.config/redmi-engineer-lab/relay.json`; it contains the local bearer token.
- Supabase service-role/secret keys must remain in server-side Edge Function environment variables.
- The local agent accepts only fixed read-only task names; arbitrary shell text and arbitrary command arguments are not supported.
- WorldMode, band selection, RF, NVRAM/NVDATA, calibration, and identity-related writes are out of scope for unattended execution.
- The relay uses per-device random bearer tokens, SHA-256 token hashes at rest, TLS, expiring commands, single-claim queue semantics, and server-side authorization.
- Device reports are redacted and size-bounded before local persistence or upload.

Report security issues privately to the repository owner. Do not publish sensitive device output in an issue.
