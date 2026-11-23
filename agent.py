#!/usr/bin/env python3
"""Read-only Redmi Engineer Lab collector and authenticated command-polling agent."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.request import HTTPRedirectHandler, build_opener
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
MAX_OUTPUT = 48_000
TIMEOUT_SECONDS = 25
POLL_SECONDS = 20
ALLOWED_TASKS = {"inventory", "telephony", "radio", "source", "connectivity"}
RISH_ENV = {
    "RISH_APPLICATION_ID": "com.termux",
    "MANAGER_APPLICATION_ID": "moe.shizuku.privileged.api",
}
RISH = str(Path.home() / "rish")

TASK_COMMANDS = {
    "inventory": [
        RISH, "-c",
        "printf 'ANDROID_RELEASE='; getprop ro.build.version.release; "
        "printf 'DEVICE='; getprop ro.product.device; "
        "printf 'MODEL='; getprop ro.product.model; "
        "printf '\\nENGINEERMODE_PACKAGE\\n'; pm path com.mediatek.engineermode; "
        "printf '\\nENGINEERMODE_COMPONENTS\\n'; dumpsys package com.mediatek.engineermode | "
        "grep -iE 'Activity|Service|Receiver|Provider|permission' | head -n 160; "
        "printf '\\nMEDIATEK_PACKAGES\\n'; pm list packages | grep -i mediatek | head -n 120"
    ],
    "telephony": [
        RISH, "-c",
        "dumpsys telephony.registry | grep -iE "
        "'mServiceState|mSignalStrength|mDataConnectionState|mDataNetworkType|mVoiceNetworkType'"
    ],
    "radio": [
        RISH, "-c",
        "logcat -b all -d -t 5000 | grep -iE "
        "'mBandMode|checkWmCapab|setWorldModeWithBand|EPBSE|Failed to query band|"
        "WorldMode|BandSelect|ATCI|AT>|AT<|CME ERROR|"
        "currentSignalStrengthWithWcdmaEcioInd|RILMUXD|RilClient|RtcRilClientController|"
        "NetworkRegistrationInfo|DataRegState|ServiceState|LTE|WCDMA|IMS|error|fail|denied' "
        "| tail -n 800"
    ],
    "connectivity": [
        RISH, "-c",
        "printf '===== CONNECTIVITY =====\\n'; dumpsys connectivity | "
        "grep -iE 'NetworkAgentInfo|TRANSPORT_CELLULAR|NetworkCapabilities|mNetworkInfo' | head -n 220; "
        "printf '\\n===== ACTIVE NETWORK =====\\n'; dumpsys netstats | head -n 80"
    ],
    "source": [
        "sh", "-c",
        "base=\\"$HOME/em_decoded\\"; eng=\\"$base/sources/com/mediatek/engineermode\\"; "
        "if [ ! -d \\"$eng\\" ] && [ ! -d \\"$base/smali/com/mediatek/engineermode\\" ]; then "
        "echo 'SOURCE_NOT_FOUND: expected JADX sources or apktool smali under ~/em_decoded'; exit 0; fi; "
        "echo '===== WORLD/BAND SOURCE FILES ====='; "
        "find \\"$base\\" -type f | grep -iE 'world.?mode|band.?select|modem|radio' | head -n 220; "
        "echo '===== WORLD/BAND VALIDATION, LISTENERS AND MODEM CALLS ====='; "
        "grep -RniE -C 5 'storeModemType|rebootModem|setModemType|WorldMode|modemType|world.mode|setWorldMode|BandSelect|setBandModeGsm|mBtnSet|mBtnReset|setOnClickListener|onClick|ATCI|sendAtCommand' "
        "\\"$base/sources/com/mediatek/engineermode\\" \\"$base/smali\\" \\"$base/smali_classes2\\" 2>/dev/null | head -n 1400; "
        "echo '===== MANIFEST PERMISSIONS/COMPONENTS ====='; "
        "for manifest in \\"$base/AndroidManifest.xml\\" \\"$base/resources/AndroidManifest.xml\\"; do "
        "if [ -f \\"$manifest\\" ]; then grep -niE 'uses-permission|activity|service|receiver|provider|exported|permission' \\"$manifest\\" | head -n 300; fi; done; "
        "echo '===== ENGINEERMODE RESOURCES ====='; "
        "for resdir in \\"$base/res\\" \\"$base/resources/res\\"; do "
        "if [ -d \\"$resdir\\" ]; then find \\"$resdir\\" -type f | grep -iE 'world|band|modem|radio' | head -n 300; fi; done"
    ],
}

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)\\bIMEI\\s*[:=]?\\s*[0-9]{14,16}\\b"),
    re.compile(r"(?i)\\bIMSI\\s*[:=]?\\s*[0-9]{14,16}\\b"),
    re.compile(r"(?i)\\bICCID\\s*[:=]?\\s*[0-9]{18,22}\\b"),
    re.compile(r"(?i)\\b(?:MEID|ESN)\\s*[:=]?\\s*[0-9A-F-]{8,18}\\b"),
    re.compile(r"(?i)\\b(?:phone|subscriber)\\s*(?:number|msisdn)\\s*[:=]?\\s*\\+?[0-9][0-9 -]{6,18}"),
    re.compile(r"(?i)\\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret[_-]?key|service[_-]?role[_-]?key|password)\\s*[:=]\\s*[^\\s,;]+"),
    re.compile(r"(?<![0-9])(?:[0-9]{14,16}|[0-9]{19,22})(?![0-9])"),
]


def redact(value: str) -> str:
    result = value
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def validate_task(task: str) -> bool:
    return task in ALLOWED_TASKS and task in TASK_COMMANDS


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
    env = os.environ.copy()
    env.update(RISH_ENV)
    try:
        completed = subprocess.run(
            TASK_COMMANDS[task],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
    except FileNotFoundError as exc:
        return "unavailable", f"Required executable not found: {exc.filename}"
    except subprocess.TimeoutExpired:
        return "timeout", f"Collection exceeded {TIMEOUT_SECONDS} seconds"
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        return "error", f"exit_code={completed.returncode}\\n{output}"
    return "ok", output or "(no output)"


def config_path() -> Path:
    return Path.home() / ".config" / "redmi-engineer-lab" / "relay.json"


def enroll() -> int:
    """Create local-only device credentials; only the UUID and hash are shared."""
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    device_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(48)
    payload = {
        "device_id": device_id,
        "token": token,
        "poll_seconds": POLL_SECONDS,
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload), encoding="utf-8")
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(path)
    try:
        path.chmod(0o600)
        path.parent.chmod(0o700)
    except OSError:
        pass
    print(json.dumps({
        "device_id": device_id,
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "label": "Redmi Note 8 Pro",
    }, indent=2))
    print("IMPORTANT: token remains local and is never printed. Share only the JSON above.")
    return 0


def load_relay_config() -> dict[str, Any]:
    path = config_path()
    if not path.is_file():
        raise RuntimeError("No local relay credentials. Run: python agent.py --enroll")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("device_id"), str) or not isinstance(data.get("token"), str):
        raise RuntimeError("Relay credentials file is invalid")
    return data


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


HTTP_OPENER = build_opener(NoRedirectHandler)


def request_json(url: str, method: str, device_id: str, token: str,
                 payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Device-Id": device_id,
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
    )
    try:
        with HTTP_OPENER.open(request, timeout=20) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise RuntimeError("Relay response exceeded size limit")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read(4096).decode("utf-8", errors="replace")
        if exc.code == 204:
            return 204, None
        raise RuntimeError(f"Relay HTTP {exc.code}: {redact(raw)}") from None


def relay_loop(relay_url: str) -> int:
    cfg = load_relay_config()
    base = relay_url.rstrip("/")
    poll_url = base + "/poll"
    complete_url = base + "/complete"
    device_id, token = cfg["device_id"], cfg["token"]
    print("Relay agent started. Read-only tasks only. Press Ctrl+C to stop.")
    while True:
        try:
            status, data = request_json(poll_url, "GET", device_id, token)
            if status == 204 or not data:
                time.sleep(POLL_SECONDS)
                continue
            command = data.get("command") if isinstance(data, dict) else None
            if not isinstance(command, dict):
                time.sleep(POLL_SECONDS)
                continue
            command_id = command.get("command_id")
            task = command.get("task")
            expires_at = command.get("expires_at")
            if not isinstance(command_id, str) or not isinstance(task, str) or not validate_task(task):
                print("Rejected malformed or non-allowlisted relay command.")
                time.sleep(POLL_SECONDS)
                continue
            if isinstance(expires_at, str):
                try:
                    deadline = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if deadline <= datetime.now(timezone.utc):
                        raise ValueError("expired")
                except ValueError:
                    print("Rejected expired/invalid relay command.")
                    time.sleep(POLL_SECONDS)
                    continue
            result_status, output = collect(task)
            report = build_report(task, result_status, output)
            request_json(
                complete_url, "POST", device_id, token,
                {"command_id": command_id, "status": result_status,
                 "result": {"report": report}},
            )
            print(f"completed task={task} status={result_status}")
        except KeyboardInterrupt:
            print("\\nRelay agent stopped.")
            return 0
        except Exception as exc:
            # Do not print credentials, request headers, or raw device output.
            print(f"relay_error={type(exc).__name__}: {redact(str(exc))[:300]}")
            time.sleep(POLL_SECONDS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", choices=sorted(ALLOWED_TASKS))
    group.add_argument("--enroll", action="store_true")
    group.add_argument("--relay", action="store_true")
    parser.add_argument("--relay-url", help="Supabase Edge Function base URL ending in /functions/v1/device-relay")
    parser.add_argument("--stdout", action="store_true", help="Print JSON instead of writing a report")
    args = parser.parse_args(argv)

    if args.enroll:
        return enroll()
    if args.relay:
        if not args.relay_url:
            parser.error("--relay requires --relay-url")
        return relay_loop(args.relay_url)

    status, output = collect(args.task)
    report = build_report(args.task, status, output)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.stdout:
        print(encoded)
    else:
        REPORT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = REPORT_DIR / f"{args.task}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        path.write_text(encoded + "\\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        print(f"report={path}")
        print(f"status={status}")
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
