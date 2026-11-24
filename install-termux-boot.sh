#!/data/data/com.termux/files/usr/bin/bash
set -eu

INSTALL_DIR="$HOME/RedmiEngineerLab"
BOOT_DIR="$HOME/.termux/boot"
SOURCE="$INSTALL_DIR/termux-boot/start-redmi-engineer-lab"
TARGET="$BOOT_DIR/start-redmi-engineer-lab"

if [ ! -f "$SOURCE" ]; then
  echo "Missing boot entry: $SOURCE" >&2
  exit 1
fi

mkdir -p "$BOOT_DIR"
chmod 700 "$HOME/.termux" "$BOOT_DIR"
cp "$SOURCE" "$TARGET"
chmod 700 "$TARGET"

echo "Installed Termux:Boot startup entry: $TARGET"
if ! pm path com.termux.boot >/dev/null 2>&1; then
  echo "Termux:Boot add-on is not detected. Install and open the official Termux:Boot app once."
else
  echo "Termux:Boot add-on detected. Startup entry is installed."
fi
echo "Android battery restrictions may still stop background execution."
