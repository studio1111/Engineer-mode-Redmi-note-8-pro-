#!/data/data/com.termux/files/usr/bin/bash
set -eu

REPO_URL="https://github.com/studio1111/Engineer-mode-Redmi-note-8-pro-.git"
INSTALL_DIR="$HOME/RedmiEngineerLab"

pkg update -y
pkg install -y git python curl

if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
python -m py_compile agent.py
python -m unittest discover -s tests -v

if [ ! -x "$HOME/rish" ]; then
  echo "WARNING: ~/rish is missing or not executable. Install/configure Shizuku Rish before diagnostics."
else
  echo "Checking Shizuku Rish access..."
  RISH_APPLICATION_ID=com.termux MANAGER_APPLICATION_ID=moe.shizuku.privileged.api "$HOME/rish" -c 'id' || {
    echo "WARNING: Rish is present but its permission check failed. Fix Shizuku authorization before running the agent."
  }
fi

if [ -f "$HOME/.config/redmi-engineer-lab/relay.json" ]; then
  echo "Existing local relay credentials found; enrollment was not overwritten."
else
  python agent.py --enroll
fi

echo
echo "Install and local tests completed. Share only the enrollment JSON (device_id + token_sha256)."
echo "Never share ~/.config/redmi-engineer-lab/relay.json; it contains the local bearer token."
