#!/data/data/com.termux/files/usr/bin/bash
set -eu

INSTALL_DIR="$HOME/RedmiEngineerLab"
STATE_DIR="$HOME/.local/state/redmi-engineer-lab"
LOG_FILE="$STATE_DIR/relay.log"
PID_FILE="$STATE_DIR/relay.pid"
URL_FILE="$STATE_DIR/relay.url"
RELAY_URL="${1:-}"

if [ -z "$RELAY_URL" ]; then
  echo "Usage: bash start-relay.sh https://PROJECT_REF.supabase.co/functions/v1/device-relay"
  exit 2
fi
case "$RELAY_URL" in
  https://*.supabase.co/functions/v1/device-relay) ;;
  *) echo "Refusing unexpected relay URL; expected the HTTPS Supabase device-relay endpoint." >&2; exit 2 ;;
esac
if [ ! -x "$INSTALL_DIR/relay-supervisor.sh" ] && [ ! -f "$INSTALL_DIR/relay-supervisor.sh" ]; then
  echo "Missing relay-supervisor.sh in $INSTALL_DIR" >&2
  exit 1
fi

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
printf '%s\n' "$RELAY_URL" > "$URL_FILE"
chmod 600 "$URL_FILE"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Relay supervisor already running (pid=$old_pid)"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

rm -f "$STATE_DIR/relay.stop"
cd "$INSTALL_DIR"
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

nohup bash "$INSTALL_DIR/relay-supervisor.sh" "$RELAY_URL" >>"$LOG_FILE" 2>&1 </dev/null &
pid=$!
echo "$pid" > "$PID_FILE"
chmod 600 "$PID_FILE" "$LOG_FILE" 2>/dev/null || true
sleep 1
if kill -0 "$pid" 2>/dev/null; then
  echo "Supervised relay started (pid=$pid)"
  echo "Worker restarts automatically after unexpected exit."
  echo "Log: $LOG_FILE"
else
  rm -f "$PID_FILE"
  echo "Relay supervisor failed to start. Inspect: $LOG_FILE"
  exit 1
fi
