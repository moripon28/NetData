# NetPulse

[English](README.md) | [日本語](README.ja.md)

NetPulse is a web app for monitoring devices and network activity on a local network using a Raspberry Pi. It shows device status and traffic in real time without storing packet contents or browsing history.

## Features

- Automatically discovers LAN devices and shows their status in a WebGL 3D view
- Monitors network traffic and system metrics from the Raspberry Pi, Windows/Linux agents, and Prometheus exporters
- Checks gateway latency, packet loss, and device availability
- Monitors local services using ICMP, TCP, and HTTP(S)
- Collects status and traffic metrics from QNAP NAS devices and routers via SNMP
- Records new devices, disconnections, reconnections, and high-load events
- Detects unusual traffic and system load based on time-of-day patterns
- Generates monitoring reports using local LLMs such as LM Studio or Ollama
- Stores history in SQLite (30 days by default) and provides live updates over WebSocket
- Exposes Prometheus-compatible metrics at `/metrics`

Traffic figures are based on NIC counters available from monitored devices. They do not represent total LAN traffic. If an agent and an exporter monitor the same IP address, their traffic is not counted twice.

## Requirements

- Raspberry Pi 5 (arm64)
- Docker Engine and the Docker Compose plugin

NetPulse runs in a single container. It uses `network_mode: host` for device discovery, requires only the `NET_RAW` capability, and uses a read-only root filesystem.

## Installation

```bash
cp .env.example .env
```

Set `WEB_AUTH_USER` and `WEB_AUTH_PASSWORD` in `.env` before starting the app.

```bash
docker compose up -d --build
docker compose ps
```

Open `http://<raspberry-pi-ip>:39080` in your browser. The initial device scan may take 1–2 minutes.

View logs or stop the app:

```bash
docker compose logs -f netpulse
docker compose down
```

History is stored in `./data/netpulse.db`. Stop the container before copying the database for backup. If you have saved an LLM API key, back up `data/.llm-settings.key` as well.

## Configuration

Copy `.env.example` to `.env` and change the settings you need.

| Variable | Default | Description |
| --- | --- | --- |
| `NETWORK_SUBNET` | Auto-detected | IPv4 subnet to scan, up to `/22` |
| `GATEWAY_HOST` | Auto-detected | Router IP address |
| `NETWORK_INTERFACE` | Auto-selected | Network interface to monitor (usually `eth0`) |
| `MONITORED_HOSTS` | Empty | Comma-separated IP addresses to check regularly |
| `PUID` / `PGID` | `1000` | Container user UID/GID; match the owner of `./data` using `id -u` / `id -g` |
| `SAMPLE_INTERVAL_SECONDS` | `2` | Live metric collection interval |
| `DISCOVERY_INTERVAL_SECONDS` | `120` | LAN discovery interval |
| `DEVICE_OFFLINE_AFTER_SECONDS` | `90` | Time before a device is marked offline, in seconds |
| `RETENTION_DAYS` | `30` | Number of days to retain history |
| `CONNECTIVITY_INTERVAL_SECONDS` | `15` | Interval for LAN and optional external probes |
| `LAN_PROBE_TARGETS` | Empty | LAN targets in `name=icmp://host`, `tcp://host:port`, or HTTP(S) URL format |
| `INTERNET_PROBES_ENABLED` | `false` | Enable DNS and external IP checks |
| `INTERNET_TARGETS` | `1.1.1.1,8.8.8.8` | External IP addresses to check |
| `DNS_SERVERS` | Gateway | DNS servers to check |
| `SNMP_ENABLED` | `false` | Enable read-only SNMP collection |
| `SNMP_TARGETS` | Empty | LAN IP addresses of QNAP devices or SNMP-enabled routers |
| `SNMP_VERSION` | `2c` | `3` for SNMPv3 authPriv, or `2c` for compatibility |
| `SNMP_PROFILE` | `generic` | `qnap` for QNAP, `generic` for routers |
| `SNMP_USERNAME` | Empty | SNMPv3 username |
| `SNMP_AUTH_PROTOCOL` | `SHA` | `SHA` or `MD5`, matching the QTS settings |
| `SNMP_AUTH_PASSWORD` | Empty | SNMPv3 authentication password |
| `SNMP_PRIV_PROTOCOL` | `DES` | `DES` (CBC-DES) or `AES`, matching the QTS settings |
| `SNMP_PRIV_PASSWORD` | Empty | SNMPv3 privacy password |
| `SNMP_TIMEOUT_SECONDS` | `2` | SNMP request timeout |
| `SNMP_INTERFACE_INDEX` | `2` | WAN interface `ifIndex` |
| `SNMP_EXTRA_OIDS` | Empty | Additional vendor-specific OIDs in `name=oid` format |
| `PROMETHEUS_EXPORTERS_ENABLED` | `false` | Scrape Prometheus exporters directly on the LAN |
| `PROMETHEUS_EXPORTER_TARGETS` | Empty | Exporter URLs in `name=http://host:port/metrics` format |
| `PROMETHEUS_EXPORTER_INTERVAL_SECONDS` | `15` | Exporter collection interval |
| `PROMETHEUS_EXPORTER_TIMEOUT_SECONDS` | `5` | Timeout per exporter |
| `AGENT_TOKEN` | Empty | Random shared secret used to sign agent requests |
| `WEB_AUTH_USER` | Empty | Basic authentication username; **required** for LAN-accessible UI/API |
| `WEB_AUTH_PASSWORD` | Empty | Basic authentication password; required with `WEB_AUTH_USER` |
| `WEB_AUTH_REQUIRED` | `true` | Refuse to start without credentials; set to `false` only for local development |
| `ANOMALY_MIN_SAMPLES` | `20` | Samples needed to establish a time-of-day baseline |
| `LLM_REPORT_ENABLED` | `false` | Enable scheduled reports using a local LLM |
| `LLM_BASE_URL` | `http://127.0.0.1:1234/v1` | OpenAI-compatible API base URL, such as LM Studio |
| `LLM_ALLOW_EXTERNAL` | `false` | Restrict LLM endpoints to local/private addresses unless set to `true` |
| `LLM_MODEL` | Empty | Model used to generate reports |
| `LLM_SYSTEM_PROMPT` | Japanese report prompt | System prompt controlling report language, role, and format |
| `LLM_API_KEY` | Empty | API key, if required by the endpoint |
| `LLM_REPORT_INTERVAL_MINUTES` | `60` | Scheduled report interval (minimum 15 minutes) |
| `LLM_REPORT_LOOKBACK_MINUTES` | `60` | Monitoring period included in each report |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `120` | LLM request timeout |
| `DEMO_MODE` | `false` | Generate demo data instead of monitoring real devices |

Apply changes with `docker compose up -d`.

## Data Sources

### Windows / Linux Agent

Set `AGENT_TOKEN` in the server's `.env` file. Generate a token with:

```bash
openssl rand -hex 32
```

Recreate the container, then open `AGENT FLEET` → `EASY SETUP` in the UI to install an agent. Use `UNINSTALL` to remove it or `MANAGE` to manage registered devices. See [agent/README.md](agent/README.md) for details.

Agents send CPU, memory, disk, temperature, load, process count, network traffic, uptime, and socket metrics. Requests are signed with HMAC-SHA256; the shared token itself is not transmitted. Packet contents and lists of remote connections are not collected.

### Prometheus Exporters

NetPulse supports `node_exporter` on Linux and `windows_exporter` on Windows. A separate Prometheus server is not required.

```dotenv
PROMETHEUS_EXPORTERS_ENABLED=true
PROMETHEUS_EXPORTER_TARGETS=linux-pc=http://192.168.10.20:9100/metrics,windows-pc=http://192.168.10.30:9182/metrics
PROMETHEUS_EXPORTER_INTERVAL_SECONDS=15
```

Use the monitored hosts' firewalls to allow exporter access only from the Raspberry Pi. Devices monitored by both an agent and an exporter appear as separate nodes in the UI.

### SNMP

NetPulse supports SNMPv3 for QNAP devices and the `generic` SNMPv2c profile for routers.

Example QNAP configuration:

```dotenv
SNMP_ENABLED=true
SNMP_TARGETS=192.168.10.20
SNMP_VERSION=3
SNMP_PROFILE=qnap
SNMP_USERNAME=netpulse
SNMP_AUTH_PROTOCOL=SHA
SNMP_AUTH_PASSWORD=your-auth-password
SNMP_PRIV_PROTOCOL=AES
SNMP_PRIV_PASSWORD=your-privacy-password
SNMP_INTERVAL_SECONDS=30
```

Match the authentication and encryption settings on your QNAP device. Use SHA and AES where available; MD5 and DES are older options. Recreate the container with `docker compose up -d --build` after changing these settings.

For routers, configure `SNMP_VERSION=2c`, `SNMP_PROFILE=generic`, `SNMP_COMMUNITY`, and `SNMP_INTERFACE_INDEX`. Add custom OIDs through `SNMP_EXTRA_OIDS`. Do not expose SNMP (UDP 161) to the internet.

Available QNAP metrics depend on the device and its configuration. SNMP credentials are not returned through the API or UI.

### LAN Service Monitoring

```dotenv
LAN_PROBE_TARGETS=gateway=icmp://192.168.10.1,nas-smb=tcp://192.168.10.20:445,nas-web=http://192.168.10.20:5000/health
```

ICMP checks latency, TCP checks connectivity, and HTTP(S) treats status codes 200–399 as successful. HTTP redirects are not followed. External IP and DNS checks are disabled by default; set `INTERNET_PROBES_ENABLED=true` only if needed.

## Local LLM Reports

Set an OpenAI-compatible API base URL and model under `LLM SETTINGS` in the UI. LM Studio and Ollama are supported. If the model list cannot be retrieved, you can enter a model name manually.

Example base URL for LM Studio on another computer:

```text
http://192.168.10.60:1234/v1
```

Allow connections to the LLM server only from the Raspberry Pi. By default, NetPulse restricts endpoints to local or private addresses. Set `LLM_ALLOW_EXTERNAL=true` only when using an external API.

Test with `ANALYZE NOW` before enabling scheduled reports. NetPulse summarizes monitoring data, sends it to the LLM, and stores the report in SQLite. Packet contents, browsing URLs, and saved API keys are not sent.

The LLM text display in `NETWORK CONSTELLATION` can show the last 3, 5, or 10 reports, or reports from the last 24 hours. API keys, when configured, are stored locally in encrypted form.

## Development and Testing

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

On Windows PowerShell, activate the virtual environment with `.\.venv\Scripts\Activate.ps1`.

Run in demo mode for local development:

```bash
DEMO_MODE=true DATA_DIR=./data WEB_AUTH_REQUIRED=false uvicorn app.main:create_app --factory --reload --port 39080
```

API documentation is available at `/docs`. Main endpoints include `/api/v1/snapshot`, `/api/v1/history`, `/api/v1/traffic`, `/api/v1/connectivity`, `/api/v1/snmp`, `/api/v1/exporters`, `/api/v1/agents`, `/api/v1/events`, `/api/v1/llm/reports`, and `/ws/live`.

## Security

NetPulse is intended for use on a trusted LAN. Because it uses `network_mode: host`, devices on the LAN can reach its UI and API.

- Set `WEB_AUTH_USER` and `WEB_AUTH_PASSWORD`. By default, NetPulse refuses to start without them.
- Use `WEB_AUTH_REQUIRED=false` only for local development.
- `/api/health`, `/agent/*`, and HMAC-authenticated agent endpoints are exempt from Basic authentication.
- Do not expose NetPulse directly to the internet. Use a VPN or an authenticated reverse proxy for remote access.
- Do not commit `.env`, the database, or encryption keys to a public repository.
