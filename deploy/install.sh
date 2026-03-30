#!/usr/bin/env bash
# deploy/install.sh — Install Hisense MQTT Bridge on Savant Smart Host
set -euo pipefail

INSTALL_DIR="/opt/hisense-bridge"
SERVICE_USER="hisense-bridge"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Hisense MQTT Bridge Installer ==="

# Create user if not exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Create install directory
echo "Installing to $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"/{src,certs}

# Copy source files
sudo cp "$SCRIPT_DIR"/src/*.py "$INSTALL_DIR/src/"
sudo cp "$SCRIPT_DIR"/requirements.txt "$INSTALL_DIR/"

# Copy certificates
if [ -d "$SCRIPT_DIR/certs" ] && [ "$(ls -A "$SCRIPT_DIR/certs" 2>/dev/null)" ]; then
    sudo cp "$SCRIPT_DIR"/certs/* "$INSTALL_DIR/certs/"
fi

# Create venv and install deps
echo "Setting up Python virtual environment..."
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

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
    'mqtt_port': 36669,
    'mqtt_username': 'hisenseservice',
    'mqtt_password': 'multimqttservice',
    'auth_token': None,
    'retry_interval_sec': 30,
    'stale_state_timeout_sec': 60,
    'source_map': None,
}
with open('$INSTALL_DIR/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
" "$TV_IP" "$TV_MAC"
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
echo "To pair with TV:"
echo "  curl -X PUT http://localhost:8642/api/auth/pair"
echo "  (Enter PIN shown on TV screen)"
echo "  curl -X PUT 'http://localhost:8642/api/auth/confirm?pin=XXXX'"
echo ""
