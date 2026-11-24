#!/data/data/com.termux/files/usr/bin/bash
set -eu

STATE_DIR="$HOME/.local/state/redmi-engineer-lab"
PID_FILE="$STATE_DIR/relay.pid"
CHILD_PID_FILE="$STATE_DIR/relay.child.pid"
STOP_FILE="$STATE_DIR/relay.stop"

mkdir -p "$STATE_DIR"
touch "$STOP_FILE"
pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    child="$(cat "$CHILD_PID_FILE" 2>/dev/null || true)"
    [ -z "$child" ] || kill -TERM "$child" 2>/dev/null || true
    kill -KILL "$pid" 2>/dev/null || true
  fi
  echo "Stopped relay supervisor (pid=$pid)"
else
  echo "Relay supervisor is not running."
fi

rm -f "$PID_FILE" "$CHILD_PID_FILE" "$STOP_FILE"
if command -v termux-wake-unlock >/dev/null 2>&1; then
  termux-wake-unlock || true
fi
