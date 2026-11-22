# Redmi Engineer Lab

Read-only-first diagnostics for Xiaomi Redmi Note 8 Pro (begonia / MediaTek MTK6785), designed to run locally in Termux.

## Safety model

- Collection only: no modem, RF, NVRAM, NVDATA, calibration, IMEI, band, or WorldMode writes.
- Tasks are selected from a fixed allowlist; arbitrary shell commands are not accepted.
- Output is bounded and common subscriber/device identifiers are redacted before reports are written.
- Shizuku/Rish is used only for explicitly listed read-only Android diagnostics.
- No credentials, tokens, private keys, or device dumps belong in this repository.

## Current status

This repository starts with the local diagnostics agent and its safety tests. The secure command relay is a separate phase: it must use authenticated, expiring, replay-resistant commands and must not be enabled until the server-side authorization and device enrollment flow have been reviewed.

## Requirements

- Android 11 or compatible Android
- Termux with Python 3
- Optional: Shizuku and the Rish shell bridge for privileged read-only snapshots

## Run

```sh
python agent.py --task inventory
python agent.py --task telephony
python agent.py --task radio
python -m unittest discover -s tests -v
```

Reports are written under `reports/`. Review and redact them before sharing.

## Roadmap

1. Local read-only inventory and diagnostic snapshots.
2. Source analysis of EngineerMode Java/Smali/XML, including WorldMode validation and BandSelect paths.
3. Secure relay protocol and device enrollment.
4. ChatGPT-accessible integration, audit trail, and approval-gated repair plans.
5. End-to-end verification on the physical device.

A green CI result validates repository code only; it does not prove that modem behavior or device-specific operations are safe.
