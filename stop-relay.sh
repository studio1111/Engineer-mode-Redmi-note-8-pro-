#!/data/data/com.termux/files/usr/bin/bash
set -eu

STATE_DIR="$HOME/.local/state/redmi-engineer-lab"
PID_FILE="$STATE_DIR/relay.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "Relay PID file not found."
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  echo "Stopped relay process (pid=$pid)"
else
  echo "Relay process is not running."
fi

rm -f "$PID_FILE"
if command -v termux-wake-unlock >/dev/null 2>&1; then
  termux-wake-unlock || true
fi
