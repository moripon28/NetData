#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo sh ./install-linux.sh [server-url]" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "This installer requires a systemd-based Linux distribution." >&2
  exit 1
fi

SERVER_URL="${1:-http://192.168.10.201:39080}"
case "$SERVER_URL" in
  http://*|https://*) ;;
  *) echo "Server must be an http:// or https:// URL." >&2; exit 1 ;;
esac
SERVER_URL=${SERVER_URL%/}
SOURCE_URL="$SERVER_URL/agent"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)
INSTALL_DIR=/opt/netpulse-agent
ENV_FILE=/etc/netpulse-agent.env
TEMP_DIR=$(mktemp -d /tmp/netpulse-agent.XXXXXX)
TTY_STATE=""

cleanup() {
  if [ -n "$TTY_STATE" ] && [ -r /dev/tty ]; then
    stty "$TTY_STATE" < /dev/tty 2>/dev/null || true
  fi
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT HUP INT TERM

fetch() {
  source_url=$1
  destination=$2
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 10 --max-time 30 "$source_url" -o "$destination"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 30 -O "$destination" "$source_url"
  else
    return 1
  fi
}

install_python() {
  echo "Installing the Python 3 runtime required by the NetPulse agent ..." >&2
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y python3
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3
  elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install python3 python3-pip
  elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm python
  else
    echo "Python 3 with venv is required, and this distribution's package manager is not supported automatically." >&2
    exit 1
  fi
}

echo "Downloading the NetPulse agent from $SERVER_URL ..." >&2
if fetch "$SOURCE_URL/netpulse_agent.py" "$TEMP_DIR/netpulse_agent.py" \
  && fetch "$SOURCE_URL/requirements.txt" "$TEMP_DIR/requirements.txt"; then
  PAYLOAD_DIR=$TEMP_DIR
elif [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/netpulse_agent.py" ] && [ -f "$SCRIPT_DIR/requirements.txt" ]; then
  echo "The server download was unavailable. Using the files next to this installer." >&2
  PAYLOAD_DIR=$SCRIPT_DIR
else
  echo "Could not download the agent files. Check that $SERVER_URL is running and reachable, and that curl or wget is installed." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  install_python
fi

VENV_CHECK="$TEMP_DIR/venv-check"
if ! python3 -m venv "$VENV_CHECK" >/dev/null 2>&1; then
  rm -rf "$VENV_CHECK"
  install_python
  python3 -m venv "$VENV_CHECK"
fi
rm -rf "$VENV_CHECK"

install -d -m 0755 "$INSTALL_DIR"
install -m 0644 "$PAYLOAD_DIR/netpulse_agent.py" "$INSTALL_DIR/netpulse_agent.py"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --disable-pip-version-check --no-cache-dir -r "$PAYLOAD_DIR/requirements.txt"

if [ ! -r /dev/tty ]; then
  echo "An interactive terminal is required to enter the enrollment token." >&2
  exit 1
fi
printf "NetPulse agent enrollment token: " > /dev/tty
TTY_STATE=$(stty -g < /dev/tty)
stty -echo < /dev/tty
IFS= read -r AGENT_TOKEN < /dev/tty
stty "$TTY_STATE" < /dev/tty
TTY_STATE=""
printf "\n" > /dev/tty

if [ "${#AGENT_TOKEN}" -lt 32 ]; then
  echo "The enrollment token must contain at least 32 characters." >&2
  exit 1
fi
case "$AGENT_TOKEN" in
  *[!A-Za-z0-9._~+/=-]*)
    echo "The enrollment token contains unsupported whitespace or control characters." >&2
    exit 1
    ;;
esac

umask 077
printf 'NETPULSE_SERVER=%s\nNETPULSE_AGENT_TOKEN=%s\nNETPULSE_INTERVAL=15\n' "$SERVER_URL" "$AGENT_TOKEN" > "$ENV_FILE"
unset AGENT_TOKEN
chmod 600 "$ENV_FILE"

cat > /etc/systemd/system/netpulse-agent.service <<EOF
[Unit]
Description=NetPulse host metrics agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$ENV_FILE
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/netpulse_agent.py
Restart=always
RestartSec=10
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now netpulse-agent.service

if systemctl is-active --quiet netpulse-agent.service; then
  echo "NetPulse agent installed and started."
  echo "Dashboard: $SERVER_URL"
  echo "Verify: systemctl status netpulse-agent --no-pager"
else
  echo "The agent was installed but did not stay running. Check: journalctl -u netpulse-agent -n 50 --no-pager" >&2
  exit 1
fi
