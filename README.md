# NetPulse

NetPulseは、Raspberry Pi 5で自宅LANを観測するローカルファーストのWebアプリケーションです。通信の中身を保存せず、ネットワークの「状態」だけを楽しく、リアルタイムに眺められるようにしています。

## できること

- 2秒ごとの受信・送信速度をライブチャートで表示
- 接続端末を自動検出し、トポロジー上を流れるパーティクルで通信を表現
- ゲートウェイの応答時間・パケットロス・オンライン端末数を表示
- Raspberry PiのCPU、メモリ、ストレージ、温度、稼働時間を監視
- 端末の新規検出、オフライン化、復帰、高負荷をイベントとして記録
- 端末に表示名・種類・信頼済みフラグを設定
- SQLiteに履歴を30日間保存（設定で変更可能）
- WebSocketでブラウザーへリアルタイム配信
- `/metrics` でPrometheus互換の主要メトリクスを公開
- DNS応答時間と複数の外部IPへの疎通を監視し、LAN障害とインターネット障害を切り分け
- SNMPv2cでルーターのWAN通信量とベンダー固有のWi-Fi OIDを収集
- HMAC署名付きWindows/Linuxエージェントから端末内部メトリクスを収集
- 時間帯別ベースラインを学習し、通信量・遅延・端末数・負荷の異常を検知

## 構成

```text
LAN端末 / Gateway
       │ ping・近隣テーブル・NIC counters
       ▼
┌──────────────────────────────┐
│ NetPulse container           │
│ Collector → SQLite → API/WS  │
│                    → Web UI  │
└──────────────────────────────┘
       │
       ▼
http://192.168.10.201:8080
```

1コンテナ構成なので、arm64のRaspberry Piでも管理しやすく、フロントエンドのビルド環境も不要です。`network_mode: host` を使い、コンテナからLANの近隣情報とICMP応答を観測します。権限は `NET_RAW` のみに限定し、コンテナのルートファイルシステムは読み取り専用です。

## Raspberry Piで起動

Docker EngineとDocker Composeプラグインがインストール済みであることを前提にしています。

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

ブラウザーで `http://192.168.10.201:8080` を開きます。初回の全端末探索には最大1〜2分かかります。

停止とログ確認:

```bash
docker compose logs -f netpulse
docker compose down
```

データベースはホスト側の `./data/netpulse.db` に残ります。バックアップはコンテナ停止中にこのファイルをコピーしてください。

## 設定

`.env.example` を `.env` にコピーし、必要な項目だけ変更します。

| 変数 | 既定値 | 内容 |
|---|---:|---|
| `NETWORK_SUBNET` | 自動検出 | 探索するIPv4サブネット。最大 `/22` |
| `GATEWAY_HOST` | 自動検出 | ルーターのIPアドレス |
| `NETWORK_INTERFACE` | 自動選択 | 監視するNIC（通常は `eth0`） |
| `MONITORED_HOSTS` | 空 | 常時確認したいIPをカンマ区切りで指定 |
| `PUID` / `PGID` | `1000` | データ保存に使うRaspberry PiユーザーのUID/GID |
| `SAMPLE_INTERVAL_SECONDS` | `2` | ライブメトリクスの収集間隔 |
| `DISCOVERY_INTERVAL_SECONDS` | `120` | LAN全体を探索する間隔 |
| `DEVICE_OFFLINE_AFTER_SECONDS` | `90` | オフラインと判断するまでの秒数 |
| `RETENTION_DAYS` | `30` | 履歴の保持日数 |
| `CONNECTIVITY_INTERVAL_SECONDS` | `15` | DNS・外部疎通の確認間隔 |
| `INTERNET_TARGETS` | `1.1.1.1,8.8.8.8` | 外部疎通先IP |
| `DNS_SERVERS` | ゲートウェイ | DNS応答確認先 |
| `SNMP_ENABLED` | `false` | 読み取り専用SNMP収集を有効化 |
| `SNMP_TARGETS` | 空 | SNMP対応ルーターのIP |
| `SNMP_INTERFACE_INDEX` | `2` | WANインターフェースのifIndex |
| `SNMP_EXTRA_OIDS` | 空 | `name=oid` 形式のWi-Fi等ベンダー固有OID |
| `AGENT_TOKEN` | 空 | エージェント署名用のランダム共有鍵 |
| `ANOMALY_MIN_SAMPLES` | `20` | 各時間帯の学習完了に必要なサンプル数 |
| `DEMO_MODE` | `false` | 実端末の代わりにデモデータを生成 |

設定変更後は `docker compose up -d` で反映します。

## 集めると良いデータ

現在の実装では、プライバシーを侵しにくく、家庭内の異常に気づきやすい次の4群を優先しています。

1. **回線の体感品質** — ゲートウェイ遅延、パケットロス、受信・送信速度。重い通信やWi-Fi不調を最初に発見できます。
2. **端末の在席情報** — IP、MAC、ホスト名、初回・最終確認時刻、オンライン状態。知らない端末や普段いる端末の消失に気づけます。
3. **監視ノードの健康** — CPU、メモリ、ディスク、温度、稼働時間。監視そのものが止まりそうな兆候を把握できます。
4. **状態変化の履歴** — 新規端末、切断、復帰、しきい値超過。瞬間的な問題を後から追跡できます。

追加実装では以下も収集します。

- **SNMP** — 標準の64bitインターフェースカウンターからWAN速度を計算します。Wi-Fiクライアント数、チャネル、信号強度はルーターごとにOIDが異なるため `SNMP_EXTRA_OIDS` で追加します。
- **DNS・外部疎通** — 指定DNSへのAレコード問い合わせと、複数の外部IPへのICMP応答を15秒周期で保存します。
- **ホストエージェント** — Windows/LinuxのCPU、メモリ、ディスク、温度、通信量、稼働時間を15秒周期で受信します。インストール方法は `agent/README.md` にあります。
- **異常検知** — ローカル時刻の時間帯ごとに平均と分散をSQLiteへ学習し、通常から大きく外れた値をイベント化します。最初の時間帯は学習完了まで約10分です。

DHCPリースやローカルのMACベンダーデータベースとの連携は、端末名の精度向上として引き続き追加可能です。

パケット本文、閲覧URL、DNSクエリ内容の常時保存は、家庭内でもプライバシーへの影響が大きいため初期実装には入れていません。必要になった場合も、対象・保持期間・閲覧権限を明確にして追加するのがおすすめです。

## SNMPを有効にする

ルーター側でSNMPv2cの読み取り専用アクセスを、Raspberry PiのIP `192.168.10.201` だけに許可します。その後 `.env` の `SNMP_ENABLED=true`、`SNMP_TARGETS`、`SNMP_COMMUNITY`、`SNMP_INTERFACE_INDEX` を設定してコンテナを再作成します。

コミュニティ文字列は秘密情報として扱い、Gitや画面へ記録しないでください。NetPulseのAPIは設定値を返さず、設定済みかどうかと収集状態だけを表示します。

## Windows/Linuxエージェント

サーバーの `.env` に32バイト以上のランダムな `AGENT_TOKEN` を設定します。各端末へ `agent` フォルダーをコピーし、[agent/README.md](agent/README.md) の手順でインストールします。トークン本体は送信せず、リクエスト本文をHMAC-SHA256で署名します。

## SQLiteで問題ない理由

この構成ではFastAPIの1プロセスだけが書き込み、ブラウザーやエージェントはAPI経由でアクセスします。SQLiteはWALモードで読み書きを並行でき、数秒周期・家庭内端末数十〜数百台の規模には十分です。管理サービスが不要で、バックアップと復旧も `data/netpulse.db` 1ファイルで行えます。

PostgreSQLへ移行する目安は、複数のNetPulseサーバーから同じDBへ同時書き込みする、毎秒数百〜数千件を長期保存する、複数ユーザーの重い分析クエリを並行実行する場合です。通常のRaspberry Pi単体運用ではSQLiteの方が単純で故障点も少なくなります。

## 開発とテスト

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

Windows PowerShellでは有効化コマンドを `.\.venv\Scripts\Activate.ps1` に読み替えてください。デモ表示は `DEMO_MODE=true` と `DATA_DIR=./data` を設定して `uvicorn app.main:app --reload --port 8080` を実行します。

API仕様は `/docs` で確認できます。主要エンドポイントは `/api/v1/snapshot`、`/api/v1/history`、`/api/v1/connectivity`、`/api/v1/snmp`、`/api/v1/agents`、`/api/v1/events`、`/ws/live` です。

## セキュリティ上の注意

このアプリは信頼できる家庭内LANでの利用を想定し、ログイン機能は持っていません。ルーターのポート転送などでインターネットへ直接公開しないでください。外部から見る場合は、VPN（WireGuard/Tailscaleなど）経由にするか、認証付きリバースプロキシを前段に置いてください。
