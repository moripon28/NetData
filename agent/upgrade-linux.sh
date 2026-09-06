#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo sh ./upgrade-linux.sh" >&2
  exit 1
fi

INSTALL_DIR=/opt/netpulse-agent
ENV_FILE=/etc/netpulse-agent.env
AGENT_FILE="$INSTALL_DIR/netpulse_agent.py"

if [ ! -f "$ENV_FILE" ]; then
  echo "Not installed: $ENV_FILE was not found. Install the agent first (install-linux.sh)." >&2
  exit 1
fi
if [ ! -f "$AGENT_FILE" ]; then
  echo "The agent script is missing at $AGENT_FILE. Install the agent first (install-linux.sh)." >&2
  exit 1
fi

SERVER_URL=$(sed -n 's/^NETPULSE_SERVER=//p' "$ENV_FILE" | head -n 1)
if [ -z "$SERVER_URL" ]; then
  echo "NETPULSE_SERVER is not set in $ENV_FILE." >&2
  exit 1
fi
case "$SERVER_URL" in
  http://*|https://*) ;;
  *) echo "NETPULSE_SERVER must be an http:// or https:// URL." >&2; exit 1 ;;
esac
SERVER_URL=${SERVER_URL%/}

TEMP_DIR=$(mktemp -d /tmp/netpulse-agent-upgrade.XXXXXX)
cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT HUP INT TERM

echo "Downloading the NetPulse agent from $SERVER_URL ..." >&2
if command -v curl >/dev/null 2>&1; then
  curl -fsSL --connect-timeout 10 --max-time 30 "$SERVER_URL/agent/netpulse_agent.py" -o "$TEMP_DIR/netpulse_agent.py"
elif command -v wget >/dev/null 2>&1; then
  wget -q -T 30 -O "$TEMP_DIR/netpulse_agent.py" "$SERVER_URL/agent/netpulse_agent.py"
else
  echo "curl or wget is required." >&2
  exit 1
fi

NEW_VERSION=$(sed -n 's/^VERSION = "\([^"]*\)".*/\1/p' "$TEMP_DIR/netpulse_agent.py" | head -n 1)
OLD_VERSION=$(sed -n 's/^VERSION = "\([^"]*\)".*/\1/p' "$AGENT_FILE" | head -n 1)
if [ -z "$NEW_VERSION" ]; then
  echo "The downloaded file does not look like a NetPulse agent (VERSION line missing)." >&2
  exit 1
fi

if [ "$NEW_VERSION" = "$OLD_VERSION" ]; then
  echo "The agent is already at version $NEW_VERSION. Nothing to do."
  exit 0
fi

cp -p "$AGENT_FILE" "$AGENT_FILE.bak"
install -m 0644 "$TEMP_DIR/netpulse_agent.py" "$AGENT_FILE"

systemctl restart netpulse-agent.service
sleep 2

if systemctl is-active --quiet netpulse-agent.service; then
  echo "NetPulse agent upgraded: $OLD_VERSION -> $NEW_VERSION"
  echo "Verify: systemctl status netpulse-agent --no-pager"
else
  echo "The agent did not stay running after the upgrade. Restoring the previous version ..." >&2
  mv -f "$AGENT_FILE.bak" "$AGENT_FILE"
  systemctl restart netpulse-agent.service
  exit 1
fi
