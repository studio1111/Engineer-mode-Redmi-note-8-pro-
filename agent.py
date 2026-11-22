#!/usr/bin/env python3
"""Read-only diagnostic collector for Redmi Engineer Lab.

No arbitrary command execution and no modem configuration writes are implemented.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
MAX_OUTPUT = 48_000
TIMEOUT_SECONDS = 25

# Fixed commands only. Do not add modem/RF/NVRAM write commands here.
TASK_COMMANDS = {
    "inventory": [
        "rish", "-c",
        "printf 'ANDROID_RELEASE='; getprop ro.build.version.release; "
        "printf 'DEVICE='; getprop ro.product.device; "
        "printf 'MODEL='; getprop ro.product.model; "
        "printf '\\nENGINEERMODE_PACKAGE\\n'; pm path com.mediatek.engineermode; "
        "printf '\\nRIL_PACKAGES\\n'; pm list packages | grep -iE 'mediatek.(ims|telephony|atci|engineermode)'"
    ],
    "telephony": [
        "rish", "-c",
        "dumpsys telephony.registry | grep -iE "
        "'mServiceState|mSignalStrength|mDataConnectionState|mDataNetworkType|mVoiceNetworkType|mCellIdentity|mCellInfo'"
    ],
    "radio": [
        "rish", "-c",
        "logcat -b radio -d -t 3000 | grep -iE "
        "'ATCI|RILMUXD|RilClient|WorldMode|BandSelect|LTE|EDGE|GSM|WCDMA|ServiceState|DataRegState|IMS|error|fail|denied' | tail -n 500"
    ],
    "source": [
        "sh", "-c",
        "if [ -d \"$HOME/em_decoded/sources/com/mediatek/engineermode\" ]; then "
        "grep -RniE 'storeModemType|rebootModem|setModemType|WorldMode|modemType|world.mode|setWorldMode|BandSelect' "
        "\"$HOME/em_decoded/sources/com/mediatek/engineermode\" 2>/dev/null | head -n 500; "
        "else echo 'SOURCE_NOT_FOUND: expected ~/em_decoded/sources/com/mediatek/engineermode'; fi"
    ],
}

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)\bIMEI\s*[:=]?\s*[0-9]{14,16}\b"),
    re.compile(r"(?i)\bIMSI\s*[:=]?\s*[0-9]{14,16}\b"),
    re.compile(r"(?i)\bICCID\s*[:=]?\s*[0-9]{18,22}\b"),
    re.compile(r"(?i)\b(?:MEID|ESN)\s*[:=]?\s*[0-9A-F-]{8,18}\b"),
    re.compile(r"(?i)\b(?:phone|subscriber)\s*(?:number|msisdn)\s*[:=]?\s*\+?[0-9][0-9 -]{6,18}"),
]


def redact(value: str) -> str:
    """Remove common subscriber identifiers before any report is persisted."""
    result = value
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def validate_task(task: str) -> bool:
    return task in TASK_COMMANDS


def build_report(task: str, status: str, output: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_profile": "redmi-note-8-pro-begonia",
        "task": task,
        "status": status,
        "read_only": True,
        "output": redact(output)[:MAX_OUTPUT],
    }


def collect(task: str) -> tuple[str, str]:
    if not validate_task(task):
        raise ValueError("Task is not in the read-only allowlist")
    command = TASK_COMMANDS[task]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        return "unavailable", f"Required executable not found: {exc.filename}"
    except subprocess.TimeoutExpired:
        return "timeout", f"Collection exceeded {TIMEOUT_SECONDS} seconds"
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        return "error", f"exit_code={completed.returncode}\n{output}"
    return "ok", output or "(no output)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=sorted(TASK_COMMANDS))
    parser.add_argument("--stdout", action="store_true", help="Print JSON instead of writing a report")
    args = parser.parse_args(argv)

    status, output = collect(args.task)
    report = build_report(args.task, status, output)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)

    if args.stdout:
        print(encoded)
    else:
        REPORT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = REPORT_DIR / f"{args.task}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        path.write_text(encoded + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        print(f"report={path}")
        print(f"status={status}")
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
