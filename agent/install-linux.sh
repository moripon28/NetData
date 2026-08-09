#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo ./install-linux.sh [server-url]" >&2
  exit 1
fi

SERVER_URL="${1:-http://192.168.10.201:39080}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR=/opt/netpulse-agent
ENV_FILE=/etc/netpulse-agent.env

printf "NetPulse agent enrollment token: " >&2
stty -echo
read -r AGENT_TOKEN
stty echo
printf "\n" >&2

mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/netpulse_agent.py" "$INSTALL_DIR/netpulse_agent.py"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --no-cache-dir -r "$SCRIPT_DIR/requirements.txt"

printf 'NETPULSE_SERVER=%s\nNETPULSE_AGENT_TOKEN=%s\nNETPULSE_INTERVAL=15\n' "$SERVER_URL" "$AGENT_TOKEN" > "$ENV_FILE"
chmod 600 "$ENV_FILE"

printf '%s\n' \
  '[Unit]' \
  'Description=NetPulse host metrics agent' \
  'After=network-online.target' \
  'Wants=network-online.target' \
  '' \
  '[Service]' \
  'Type=simple' \
  "EnvironmentFile=$ENV_FILE" \
  "ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/netpulse_agent.py" \
  'Restart=always' \
  'RestartSec=10' \
  'NoNewPrivileges=true' \
  'ProtectSystem=strict' \
  'ProtectHome=true' \
  'PrivateTmp=true' \
  '' \
  '[Install]' \
  'WantedBy=multi-user.target' > /etc/systemd/system/netpulse-agent.service

systemctl daemon-reload
systemctl enable --now netpulse-agent.service
echo "NetPulse agent installed and started."
