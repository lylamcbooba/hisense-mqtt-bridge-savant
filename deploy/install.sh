#!/usr/bin/env bash
# deploy/install.sh — Install Hisense Android TV Bridge on Savant Smart Host
set -euo pipefail

INSTALL_DIR="/opt/hisense-bridge"
SERVICE_USER="hisense-bridge"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Hisense Android TV Bridge Installer ==="

# Create user if not exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    NOLOGIN=$(command -v nologin 2>/dev/null || echo /bin/false)
    sudo useradd --system --no-create-home --shell "$NOLOGIN" "$SERVICE_USER"
fi

# Create install directory
echo "Installing to $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"/{src,certs}

# Copy source files
sudo cp "$SCRIPT_DIR"/src/*.py "$INSTALL_DIR/src/"
sudo cp "$SCRIPT_DIR"/requirements.txt "$INSTALL_DIR/"

# Create venv and install deps
echo "Setting up Python virtual environment..."
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install -q --upgrade pip
sudo "$INSTALL_DIR/venv/bin/pip" install -q --extra-index-url https://www.piwheels.org/simple -r "$INSTALL_DIR/requirements.txt"

# Configure TV connection
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    read -rp "TV IP address: " TV_IP
    read -rp "TV MAC address (AA:BB:CC:DD:EE:FF): " TV_MAC
    sudo "$INSTALL_DIR/venv/bin/python3" -c "
import json, sys
cfg = {
    'tv_ip': sys.argv[1],
    'tv_mac': sys.argv[2],
    'bind_address': '127.0.0.1',
    'bridge_port': 8642,
    'client_id': 'SavantHost',
    'api_port': 6466,
    'pair_port': 6467,
    'source_map': {
        'HDMI1': 'KEYCODE_TV_INPUT_HDMI_1',
        'HDMI2': 'KEYCODE_TV_INPUT_HDMI_2',
        'HDMI3': 'KEYCODE_TV_INPUT_HDMI_3',
        'HDMI4': 'KEYCODE_TV_INPUT_HDMI_4',
        'Apps': 'KEYCODE_HOME',
    },
}
with open(sys.argv[3], 'w') as f:
    json.dump(cfg, f, indent=2)
" "$TV_IP" "$TV_MAC" "$INSTALL_DIR/config.json"
else
    echo "Config already exists, skipping..."
fi

# Set permissions
sudo chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
sudo chmod 600 "$INSTALL_DIR/config.json"

# Install systemd service
echo "Installing systemd service..."
sudo cp "$SCRIPT_DIR/deploy/hisense-bridge.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hisense-bridge
sudo systemctl start hisense-bridge

echo ""
echo "=== Installation complete ==="
echo "Service status: sudo systemctl status hisense-bridge"
echo "View logs:      sudo journalctl -u hisense-bridge -f"
echo ""
echo "To pair with TV (TV must be on):"
echo "  curl -X PUT http://localhost:8642/api/auth/pair"
echo "  (Enter 6-character code shown on TV screen)"
echo "  curl -X PUT 'http://localhost:8642/api/auth/confirm?pin=XXXXXX'"
echo ""
