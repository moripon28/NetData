# NetPulse

[English](README.md) | [日本語](README.ja.md)

NetPulseは、Raspberry PiでLAN内の端末や通信状況を監視するWebアプリケーションです。端末の状態や通信量をリアルタイムに表示します。パケットの内容や閲覧履歴は保存しません。

## 主な機能

- LAN内の端末を自動検出し、接続状況をWebGLの3D画面に表示
- Raspberry Pi、Windows/Linuxエージェント、Prometheus exporterの通信量やシステム情報を監視
- ゲートウェイの応答時間、パケットロス、端末のオンライン状態を確認
- ICMP、TCP、HTTP(S)でLAN内サービスを監視
- SNMPでQNAP NASやルーターの状態・通信量を取得
- 端末の新規検出、切断、復帰、高負荷をイベントとして記録
- 時間帯ごとの傾向から通信量や負荷の異常を検知
- ローカルLLM（LM Studio、Ollamaなど）による監視レポートの作成
- SQLiteへの履歴保存（既定30日）、WebSocketによるリアルタイム更新
- Prometheus互換の `/metrics` を公開

通信量の表示は、監視対象から取得できたNICカウンターに基づきます。LAN全体の通信量を測定するものではありません。同じIPをエージェントとexporterの両方で監視していても、通信量は二重に加算しません。

## 動作環境

- Raspberry Pi 5（arm64）
- Docker Engine、Docker Composeプラグイン

アプリは単一コンテナで動作します。LAN内の端末検出に `network_mode: host` を使用し、権限は `NET_RAW` に限定しています。コンテナのルートファイルシステムは読み取り専用です。

## インストール

```bash
cp .env.example .env
```

`.env` の `WEB_AUTH_USER` と `WEB_AUTH_PASSWORD` を設定してから起動してください。

```bash
docker compose up -d --build
docker compose ps
```

ブラウザーから `http://<Raspberry PiのIP>:39080` にアクセスします。初回の端末探索には1〜2分ほどかかる場合があります。

ログ確認・停止:

```bash
docker compose logs -f netpulse
docker compose down
```

履歴は `./data/netpulse.db` に保存されます。バックアップする際はコンテナを停止してからコピーしてください。LLMのAPIキーを保存している場合は `data/.llm-settings.key` も一緒に保管してください。

## 設定

`.env.example` を `.env` にコピーし、必要な項目を変更します。

| 変数                                 | 既定値                    | 内容                                                                                |
| -------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------- |
| `NETWORK_SUBNET`                       | 自動検出                       | 探索するIPv4サブネット。最大 `/22`                                                                |
| `GATEWAY_HOST`                         | 自動検出                       | ルーターのIPアドレス                                                                           |
| `NETWORK_INTERFACE`                    | 自動選択                       | 監視するNIC（通常は `eth0`）                                                                   |
| `MONITORED_HOSTS`                      | 空                          | 常時確認したいIPをカンマ区切りで指定                                                                   |
| `PUID` / `PGID`                        | `1000`                     | 実行するコンテナユーザーのUID/GID（既定の`netpulse`ユーザーに上書き）。`./data` の所有者と合わせ、`id -u` / `id -g` の値を指定 |
| `SAMPLE_INTERVAL_SECONDS`              | `2`                        | ライブメトリクスの収集間隔                                                                         |
| `DISCOVERY_INTERVAL_SECONDS`           | `120`                      | LAN全体を探索する間隔                                                                          |
| `DEVICE_OFFLINE_AFTER_SECONDS`         | `90`                       | オフラインと判断するまでの秒数                                                                       |
| `RETENTION_DAYS`                       | `30`                       | 履歴の保持日数                                                                               |
| `CONNECTIVITY_INTERVAL_SECONDS`        | `15`                       | LANおよび任意の外部プローブ間隔                                                                     |
| `LAN_PROBE_TARGETS`                    | 空                          | `name=icmp://host`、`tcp://host:port`、HTTP(S) URLのLAN監視対象                              |
| `INTERNET_PROBES_ENABLED`              | `false`                    | DNS・外部IPへのプローブを明示的に有効化                                                                |
| `INTERNET_TARGETS`                     | `1.1.1.1,8.8.8.8`          | 外部疎通先IP                                                                               |
| `DNS_SERVERS`                          | ゲートウェイ                     | DNS応答確認先                                                                              |
| `SNMP_ENABLED`                         | `false`                    | 読み取り専用SNMP収集を有効化                                                                      |
| `SNMP_TARGETS`                         | 空                          | QNAPまたはSNMP対応ルーターのLAN内IP                                                              |
| `SNMP_VERSION`                         | `2c`                       | `3`でSNMPv3 authPriv、`2c`で従来互換                                                         |
| `SNMP_PROFILE`                         | `generic`                  | QNAPでは`qnap`、ルーターでは`generic`                                                          |
| `SNMP_USERNAME`                        | 空                          | SNMPv3ユーザー名                                                                           |
| `SNMP_AUTH_PROTOCOL`                   | `SHA`                      | QTS側と同じ`SHA`または`MD5`                                                                  |
| `SNMP_AUTH_PASSWORD`                   | 空                          | SNMPv3認証パスワード                                                                         |
| `SNMP_PRIV_PROTOCOL`                   | `DES`                      | QTS側と同じ`DES`（CBC-DES）または`AES`                                                         |
| `SNMP_PRIV_PASSWORD`                   | 空                          | SNMPv3プライバシーパスワード                                                                     |
| `SNMP_TIMEOUT_SECONDS`                 | `2`                        | SNMP要求のタイムアウト                                                                         |
| `SNMP_INTERFACE_INDEX`                 | `2`                        | WANインターフェースのifIndex                                                                   |
| `SNMP_EXTRA_OIDS`                      | 空                          | `name=oid` 形式のWi-Fi等ベンダー固有OID                                                         |
| `PROMETHEUS_EXPORTERS_ENABLED`         | `false`                    | LAN内のPrometheus exporterを直接スクレイプ                                                      |
| `PROMETHEUS_EXPORTER_TARGETS`          | 空                          | `name=http://host:port/metrics`形式の対象一覧                                                |
| `PROMETHEUS_EXPORTER_INTERVAL_SECONDS` | `15`                       | exporterの収集間隔                                                                         |
| `PROMETHEUS_EXPORTER_TIMEOUT_SECONDS`  | `5`                        | exporter 1台あたりのタイムアウト                                                                 |
| `AGENT_TOKEN`                          | 空                          | エージェント署名用のランダム共有鍵                                                                     |
| `WEB_AUTH_USER`                        | 空                          | Basic認証のユーザー名。UI/APIはLAN全体から到達可能なので**必須**                                             |
| `WEB_AUTH_PASSWORD`                    | 空                          | Basic認証のパスワード。`WEB_AUTH_USER`と併せて必須                                                   |
| `WEB_AUTH_REQUIRED`                    | `true`                     | 認証不足時に起動を拒否するか。ローカル開発で認証なし起動する場合だけ`false`                                             |
| `ANOMALY_MIN_SAMPLES`                  | `20`                       | 各時間帯の学習完了に必要なサンプル数                                                                    |
| `LLM_REPORT_ENABLED`                   | `false`                    | ローカルLLMによる定期報告を有効化                                                                    |
| `LLM_BASE_URL`                         | `http://127.0.0.1:1234/v1` | LM Studio等のOpenAI互換Base URL                                                           |
| `LLM_ALLOW_EXTERNAL`                   | `false`                    | `true`にするまでBase URLはLAN内アドレス（ループバック/プライベート）に限定                                        |
| `LLM_MODEL`                            | 空                          | 報告に使う生成モデル名                                                                           |
| `LLM_SYSTEM_PROMPT`                    | 日本語の運用報告用                  | 報告言語・役割・構成を指定するシステムプロンプト                                                              |
| `LLM_API_KEY`                          | 空                          | 接続先が要求する場合だけ設定するAPIキー                                                                 |
| `LLM_REPORT_INTERVAL_MINUTES`          | `60`                       | 定期報告の実行間隔（最短15分）                                                                      |
| `LLM_REPORT_LOOKBACK_MINUTES`          | `60`                       | 1回の報告で分析する監視期間                                                                        |
| `LLM_REQUEST_TIMEOUT_SECONDS`          | `120`                      | ローカルLLM応答の待機秒数                                                                        |
| `DEMO_MODE`                            | `false`                    | 実端末の代わりにデモデータを生成                                                                      |

変更後は `docker compose up -d` で反映します。

## データの取得方法

### Windows / Linuxエージェント

サーバーの `.env` に `AGENT_TOKEN` を設定します。トークンは次のコマンドで生成できます。

```bash
openssl rand -hex 32
```

設定後にコンテナを再作成し、画面の `AGENT FLEET` → `EASY SETUP` からエージェントをインストールします。削除は `UNINSTALL`、登録済み端末の管理は `MANAGE` から行えます。詳しくは [agent/README.md](agent/README.md) を参照してください。

エージェントはCPU、メモリ、ディスク、温度、負荷、プロセス数、通信量、稼働時間、ソケット数などを送信します。リクエスト本文はHMAC-SHA256で署名され、共有トークン自体は送信されません。通信内容や接続先の一覧は取得しません。

### Prometheus exporter

Linuxの `node_exporter` とWindowsの `windows_exporter` に対応しています。Prometheusサーバーは不要です。

```dotenv
PROMETHEUS_EXPORTERS_ENABLED=true
PROMETHEUS_EXPORTER_TARGETS=linux-pc=http://192.168.10.20:9100/metrics,windows-pc=http://192.168.10.30:9182/metrics
PROMETHEUS_EXPORTER_INTERVAL_SECONDS=15
```

各exporterへのアクセスはRaspberry Piからのみ許可するよう、監視対象のファイアウォールで制限してください。エージェントとexporterを併用した端末は、画面上で別ノードとして表示されます。

### SNMP

QNAPにはSNMPv3、ルーターにはSNMPv2cの `generic` プロファイルを利用できます。

QNAPの設定例:

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

認証・暗号化方式はQNAP側の設定と合わせてください。QTS側で利用できる方式を指定してください。MD5やDESは古い方式なので、対応している場合はSHAやAESを使ってください。設定後は `docker compose up -d --build` で再作成します。

ルーターの場合は `SNMP_VERSION=2c`、`SNMP_PROFILE=generic`、`SNMP_COMMUNITY`、`SNMP_INTERFACE_INDEX` を設定します。追加のOIDは `SNMP_EXTRA_OIDS` で指定できます。SNMPのポート（UDP 161）をインターネットに公開しないでください。

取得できるQNAPの指標は機種や構成によって異なります。SNMPの認証情報はAPIや画面には出力されません。

### LANサービス監視

```dotenv
LAN_PROBE_TARGETS=gateway=icmp://192.168.10.1,nas-smb=tcp://192.168.10.20:445,nas-web=http://192.168.10.20:5000/health
```

ICMPは応答時間、TCPは接続可否、HTTP(S)はステータスコード200〜399を確認します。HTTPリダイレクトは追跡しません。外部IPとDNSの確認は既定で無効です。必要な場合だけ `INTERNET_PROBES_ENABLED=true` を設定してください。

## ローカルLLMレポート

画面の `LLM SETTINGS` でOpenAI互換APIのBase URLとモデルを指定します。LM StudioやOllamaを利用できます。モデル一覧が取得できない場合は手入力も可能です。

別PCでLM Studioを動かす場合のBase URLの例:

```text
http://192.168.10.60:1234/v1
```

LLMサーバー側では、Raspberry Piからの接続だけを許可してください。既定では接続先をローカル・プライベートアドレスに制限しています。外部APIを使う場合のみ `LLM_ALLOW_EXTERNAL=true` を設定します。

`ANALYZE NOW` で動作確認後、定期レポートを有効にできます。監視データを集計してLLMへ送り、結果をSQLiteに保存します。パケット内容、閲覧URL、保存済みAPIキーは送信しません。

`NETWORK CONSTELLATION` のLLMテキスト表示は、直近3回・5回・10回・24時間分から選択できます。APIキーを設定した場合はローカルで暗号化して保存されます。

## 開発とテスト

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

Windows PowerShellでは `.\.venv\Scripts\Activate.ps1` で仮想環境を有効にします。

デモモードでの起動例（ローカル開発用）:

```bash
DEMO_MODE=true DATA_DIR=./data WEB_AUTH_REQUIRED=false uvicorn app.main:create_app --factory --reload --port 39080
```

API仕様は `/docs` で確認できます。主なエンドポイントは `/api/v1/snapshot`、`/api/v1/history`、`/api/v1/traffic`、`/api/v1/connectivity`、`/api/v1/snmp`、`/api/v1/exporters`、`/api/v1/agents`、`/api/v1/events`、`/api/v1/llm/reports`、`/ws/live` です。

## セキュリティ

NetPulseは信頼できるLAN内での利用を想定しています。`network_mode: host` を使用するため、UIとAPIにはLAN内の端末から接続できます。

- `WEB_AUTH_USER` と `WEB_AUTH_PASSWORD` の設定が必須です。未設定の場合は既定で起動を拒否します。
- 認証を無効にする `WEB_AUTH_REQUIRED=false` はローカル開発時に限って使用してください。
- `/api/health`、`/agent/*`、HMACで認証するエージェント用エンドポイントはBasic認証の対象外です。
- インターネットへ直接公開しないでください。外部からの利用にはVPNや認証付きリバースプロキシを使用してください。
- `.env`、データベース、暗号鍵を公開リポジトリへコミットしないでください。
