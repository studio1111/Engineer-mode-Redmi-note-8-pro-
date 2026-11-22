#!/data/data/com.termux/files/usr/bin/bash
set -eu

INSTALL_DIR="$HOME/RedmiEngineerLab"
STATE_DIR="$HOME/.local/state/redmi-engineer-lab"
LOG_FILE="$STATE_DIR/relay.log"
PID_FILE="$STATE_DIR/relay.pid"
RELAY_URL="${1:-}"

if [ -z "$RELAY_URL" ]; then
  echo "Usage: bash start-relay.sh https://PROJECT_REF.supabase.co/functions/v1/device-relay"
  exit 2
fi

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Relay already running (pid=$old_pid)"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

cd "$INSTALL_DIR"
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

nohup python agent.py --relay --relay-url "$RELAY_URL" >>"$LOG_FILE" 2>&1 </dev/null &
pid=$!
echo "$pid" > "$PID_FILE"
chmod 600 "$PID_FILE" "$LOG_FILE" 2>/dev/null || true
sleep 1
if kill -0 "$pid" 2>/dev/null; then
  echo "Relay started (pid=$pid)"
  echo "Log: $LOG_FILE"
else
  echo "Relay failed to start. Inspect: $LOG_FILE"
  exit 1
fi
