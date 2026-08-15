#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo sh ./uninstall-linux.sh" >&2
  exit 1
fi

SERVICE_NAME=netpulse-agent.service
SERVICE_FILE=/etc/systemd/system/netpulse-agent.service
INSTALL_DIR=/opt/netpulse-agent
ENV_FILE=/etc/netpulse-agent.env

if command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
fi

if [ -f "$SERVICE_FILE" ]; then
  rm -f -- "$SERVICE_FILE"
  echo "Removed service unit: $SERVICE_FILE"
else
  echo "Service unit was already absent: $SERVICE_FILE"
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload
  systemctl reset-failed "$SERVICE_NAME" >/dev/null 2>&1 || true
fi

if [ -d "$INSTALL_DIR" ]; then
  rm -rf -- "$INSTALL_DIR"
  echo "Removed agent files: $INSTALL_DIR"
else
  echo "Agent files were already absent: $INSTALL_DIR"
fi

if [ -f "$ENV_FILE" ]; then
  rm -f -- "$ENV_FILE"
  echo "Removed agent configuration: $ENV_FILE"
else
  echo "Agent configuration was already absent: $ENV_FILE"
fi

echo "NetPulse agent uninstalled."
echo "The saved server-side device record is unchanged. Remove it from AGENT FLEET > MANAGE if it is no longer needed."
