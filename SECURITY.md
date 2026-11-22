# Security Policy

## Scope

This project collects diagnostic information from an Android device. Treat radio logs, telephony state, and source dumps as potentially sensitive.

## Rules

- Never commit IMEI, IMSI, ICCID, phone numbers, SIM identifiers, authentication tokens, relay secrets, or raw unredacted device dumps.
- Keep the repository private before adding deployment configuration or any device enrollment material.
- The local agent is read-only. Do not add arbitrary shell execution or modem configuration commands.
- WorldMode, band selection, RF, NVRAM/NVDATA, calibration, and identity-related writes are out of scope for unattended execution.
- Any future relay must use TLS, per-device authentication, short-lived signed commands, nonce/replay protection, strict task allowlists, audit logging, and explicit approval for privileged operations.

Report security issues privately to the repository owner. Do not publish sensitive device output in an issue.
