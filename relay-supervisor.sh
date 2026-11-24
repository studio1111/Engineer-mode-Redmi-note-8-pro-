#!/data/data/com.termux/files/usr/bin/bash
set -u

INSTALL_DIR="$HOME/RedmiEngineerLab"
STATE_DIR="$HOME/.local/state/redmi-engineer-lab"
STOP_FILE="$STATE_DIR/relay.stop"
CHILD_PID_FILE="$STATE_DIR/relay.child.pid"
RELAY_URL="${1:-}"

if [ -z "$RELAY_URL" ]; then
  echo "Missing relay URL" >&2
  exit 2
fi

mkdir -p "$STATE_DIR"
rm -f "$STOP_FILE"
child_pid=""
cleanup() {
  touch "$STOP_FILE"
  if [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null; then
    kill -TERM "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  rm -f "$CHILD_PID_FILE"
}
trap cleanup EXIT TERM INT

delay=5
while [ ! -f "$STOP_FILE" ]; do
  cd "$INSTALL_DIR" || exit 1
  python agent.py --relay --relay-url "$RELAY_URL" &
  child_pid=$!
  printf '%s\n' "$child_pid" > "$CHILD_PID_FILE"
  wait "$child_pid"
  rc=$?
  child_pid=""
  rm -f "$CHILD_PID_FILE"

  [ -f "$STOP_FILE" ] && break
  echo "Relay worker exited (code=$rc); restarting in ${delay}s"
  sleep "$delay" &
  sleeper=$!
  wait "$sleeper" || true
  if [ "$delay" -lt 60 ]; then
    delay=$((delay * 2))
    [ "$delay" -gt 60 ] && delay=60
  fi
done
rm -f "$STOP_FILE"
