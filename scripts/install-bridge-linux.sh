#!/usr/bin/env bash
# Install the Codex RLCD bridge as a systemd user service.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE_DIR="$REPO_ROOT/bridge"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_FILE="$UNIT_DIR/rlcd-bridge.service"

command -v uv >/dev/null 2>&1 || {
    echo "error: uv is required: https://docs.astral.sh/uv/" >&2
    exit 1
}
mkdir -p "$UNIT_DIR"
UV_BIN="$(command -v uv)"

cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Codex usage and weather bridge for ESP32-S3-RLCD-4.2
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BRIDGE_DIR
EnvironmentFile=-$BRIDGE_DIR/.env
ExecStart=$UV_BIN run python bridge.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now rlcd-bridge.service
echo "Installed: $UNIT_FILE"
echo "Status: systemctl --user status rlcd-bridge"
