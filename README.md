# NetPulse

NetPulseは、Raspberry Pi 5で自宅LANを観測するローカルファーストのWebアプリケーションです。通信の中身を保存せず、ネットワークの「状態」だけを楽しく、リアルタイムに眺められるようにしています。

## できること

- Pi本体・Agent・Prometheus Exporterの受信／送信速度を合計または端末別タブでライブ表示
- 接続端末を自動検出し、深度テスト・透視投影・法線ライティングを使うWebGL 3D空間へGPUメッシュとノードカードを表示
- 観測方式別リンクに加え、通信量を取得できるノードからGatewayへNIC合計通信量のルートを表示。増加に応じて色・発光・パルス速度を強め、Gatewayより先は推測せず省略
- RP5、エージェント、対応するPrometheus Exporterの1分負荷・プロセス数・INETソケット集計を表示
- ゲートウェイの応答時間・パケットロス・オンライン端末数を表示
- Raspberry PiのCPU、メモリ、ストレージ、温度、稼働時間を監視
- 端末の新規検出、オフライン化、復帰、高負荷をイベントとして記録
- 端末に表示名・種類・信頼済みフラグを設定
- SQLiteに履歴を30日間保存（設定で変更可能）
- WebSocketでブラウザーへリアルタイム配信
- `/metrics` でPrometheus互換の主要メトリクスを公開
- LAN内サービスをICMP・TCP・HTTP(S)で監視し、必要な場合だけDNS・外部IP疎通も確認
- SNMPv3でQNAPのCPU・温度・メモリ・ディスク・RAID・プール・ボリュームを収集
- SNMPv2c互換プロファイルでルーターのWAN通信量とベンダー固有OIDを収集
- HMAC署名付きWindows/Linuxエージェントから端末内部メトリクスを収集
- LAN内のnode_exporter / windows_exporterを直接スクレイプして端末内部メトリクスを収集
- 時間帯別ベースラインを学習し、通信量・遅延・端末数・負荷の異常を検知
- OpenAI互換のローカルLLMで監視結果を定期分析し、日本語の運用報告として保存・表示

## 構成

```text
LAN端末 / Gateway / QNAP / Prometheus exporters
       │ ping・近隣テーブル・SNMPv3・NIC counters・HTTP scrape
       ▼
┌──────────────────────────────┐
│ NetPulse container           │
│ Collector → SQLite → API/WS  │
│           → LLM集約 → Report │
│                    → Web UI  │
└──────────────────────────────┘
       │
       ▼
http://192.168.10.201:39080
```

1コンテナ構成なので、arm64のRaspberry Piでも管理しやすく、フロントエンドのビルド環境も不要です。`network_mode: host` を使い、コンテナからLANの近隣情報とICMP応答を観測します。権限は `NET_RAW` のみに限定し、コンテナのルートファイルシステムは読み取り専用です。

## Raspberry Piで起動

Docker EngineとDocker Composeプラグインがインストール済みであることを前提にしています。

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

ブラウザーで `http://192.168.10.201:39080` を開きます。初回の全端末探索には最大1〜2分かかります。

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
| `CONNECTIVITY_INTERVAL_SECONDS` | `15` | LANおよび任意の外部プローブ間隔 |
| `LAN_PROBE_TARGETS` | 空 | `name=icmp://host`、`tcp://host:port`、HTTP(S) URLのLAN監視対象 |
| `INTERNET_PROBES_ENABLED` | `false` | DNS・外部IPへのプローブを明示的に有効化 |
| `INTERNET_TARGETS` | `1.1.1.1,8.8.8.8` | 外部疎通先IP |
| `DNS_SERVERS` | ゲートウェイ | DNS応答確認先 |
| `SNMP_ENABLED` | `false` | 読み取り専用SNMP収集を有効化 |
| `SNMP_TARGETS` | 空 | QNAPまたはSNMP対応ルーターのLAN内IP |
| `SNMP_VERSION` | `2c` | `3`でSNMPv3 authPriv、`2c`で従来互換 |
| `SNMP_PROFILE` | `generic` | QNAPでは`qnap`、ルーターでは`generic` |
| `SNMP_USERNAME` | 空 | SNMPv3ユーザー名 |
| `SNMP_AUTH_PROTOCOL` | `SHA` | QTS側と同じ`SHA`または`MD5` |
| `SNMP_AUTH_PASSWORD` | 空 | SNMPv3認証パスワード |
| `SNMP_PRIV_PROTOCOL` | `DES` | QTS側と同じ`DES`（CBC-DES）または`AES` |
| `SNMP_PRIV_PASSWORD` | 空 | SNMPv3プライバシーパスワード |
| `SNMP_TIMEOUT_SECONDS` | `2` | SNMP要求のタイムアウト |
| `SNMP_INTERFACE_INDEX` | `2` | WANインターフェースのifIndex |
| `SNMP_EXTRA_OIDS` | 空 | `name=oid` 形式のWi-Fi等ベンダー固有OID |
| `PROMETHEUS_EXPORTERS_ENABLED` | `false` | LAN内のPrometheus exporterを直接スクレイプ |
| `PROMETHEUS_EXPORTER_TARGETS` | 空 | `name=http://host:port/metrics`形式の対象一覧 |
| `PROMETHEUS_EXPORTER_INTERVAL_SECONDS` | `15` | exporterの収集間隔 |
| `PROMETHEUS_EXPORTER_TIMEOUT_SECONDS` | `5` | exporter 1台あたりのタイムアウト |
| `AGENT_TOKEN` | 空 | エージェント署名用のランダム共有鍵 |
| `ANOMALY_MIN_SAMPLES` | `20` | 各時間帯の学習完了に必要なサンプル数 |
| `LLM_REPORT_ENABLED` | `false` | ローカルLLMによる定期報告を有効化 |
| `LLM_BASE_URL` | `http://127.0.0.1:1234/v1` | LM Studio等のOpenAI互換Base URL |
| `LLM_MODEL` | 空 | 報告に使う生成モデル名 |
| `LLM_SYSTEM_PROMPT` | 日本語の運用報告用 | 報告言語・役割・構成を指定するシステムプロンプト |
| `LLM_API_KEY` | 空 | 接続先が要求する場合だけ設定するAPIキー |
| `LLM_REPORT_INTERVAL_MINUTES` | `60` | 定期報告の実行間隔（最短15分） |
| `LLM_REPORT_LOOKBACK_MINUTES` | `60` | 1回の報告で分析する監視期間 |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `120` | ローカルLLM応答の待機秒数 |
| `DEMO_MODE` | `false` | 実端末の代わりにデモデータを生成 |

設定変更後は `docker compose up -d` で反映します。

## 集めると良いデータ

現在の実装では、プライバシーを侵しにくく、家庭内の異常に気づきやすい次の4群を優先しています。

1. **監視ノードの通信状態** — ゲートウェイ遅延、パケットロス、Raspberry Pi自身の受信・送信速度。監視ノードや経路の異常を最初に発見できます。
2. **端末の在席情報** — IP、MAC、ホスト名、初回・最終確認時刻、オンライン状態。知らない端末や普段いる端末の消失に気づけます。
3. **監視ノードの健康** — CPU、メモリ、ディスク、温度、稼働時間。監視そのものが止まりそうな兆候を把握できます。
4. **状態変化の履歴** — 新規端末、切断、復帰、しきい値超過。瞬間的な問題を後から追跡できます。

追加実装では以下も収集します。

- **QNAP SNMP** — QTS-MIBの`1.3.6.1.4.1.55062.1`からCPU、温度、メモリ、ファン、電源、ディスク、RAID、ストレージプール、ボリューム、SSDキャッシュ、UPSを収集します。NASとディスクのシリアル番号、iSCSI情報、SMART生値は要求・保存しません。
- **ルーターSNMP** — `generic`プロファイルでは標準の64bitインターフェースカウンターからWAN速度を計算します。Wi-Fi等は`SNMP_EXTRA_OIDS`で追加できます。
- **LANサービス監視** — LAN内のICMP、TCPポート、HTTP(S)応答を15秒周期で保存します。外部ICMP・DNSは明示的に有効化した場合だけ実行します。
- **ホストエージェント** — Windows/LinuxのCPU、メモリ、ディスク、温度、1分負荷、プロセス数、通信量、稼働時間、INETソケット集計を15秒周期で受信します。接続先アドレス、ポート一覧、通信内容は送信しません。インストール方法は `agent/README.md` にあります。
- **Prometheus exporter** — 管理対象Linux/Windowsの既存exporterからCPU、メモリ、ディスク、温度、稼働時間、端末自身のNIC通信量を取得します。Exporterが公開する場合は1分負荷、プロセス数、ソケット総数、確立済みTCP数も取得します。
- **異常検知** — ローカル時刻の時間帯ごとに平均と分散をSQLiteへ学習し、通常から大きく外れた値をイベント化します。最初の時間帯は学習完了まで約10分です。

DHCPリースやローカルのMACベンダーデータベースとの連携は、端末名の精度向上として引き続き追加可能です。

パケット本文、閲覧URL、DNSクエリ内容の常時保存は、家庭内でもプライバシーへの影響が大きいため初期実装には入れていません。必要になった場合も、対象・保持期間・閲覧権限を明確にして追加するのがおすすめです。

TRAFFIC STREAMの既定値は、Raspberry Pi本体とオンラインのAgent／Prometheus Exporterから取得できたNIC通信量の合計です。横スクロール式のタブで端末別の履歴へ切り替えられ、同じIPをAgentとExporterの両方で監視している場合は二重加算しません。各値はそのホスト自身が送受信した量であり、ルーターを通るLAN全体の通信量、管理外端末ごとの実通信量、Wi-Fi無線統計を表すものではありません。これらが必要な場合は、ルーター/APのSNMPまたはAPI、管理スイッチのポートミラー、インライン観測点のいずれかが別途必要です。

## ローカルLLM報告を有効にする

vulnintelと同じく、LM StudioやOllamaなどのOpenAI互換APIを利用します。画面右上の `LLM SETTINGS` を開き、Base URLを入力して `一覧取得` を押すと、LLMサーバーが公開している生成モデルを選べます。LM Studioのnative APIも補助的に参照するため、embeddingモデルは候補から除外されます。一覧取得に失敗してもモデル名は手入力できます。システムプロンプトも画面から編集でき、既定値は出力全体を日本語に限定しています。

LM Studioを別のWindows/Linux PCで動かす場合は、サーバーをLANから接続可能にし、Base URLへ `http://<LLM-PCのLAN IP>:1234/v1` を指定します。PCのファイアウォールではTCP 1234をRaspberry Pi `192.168.10.201` からだけ許可してください。インターネット上のAPIを指定することも技術的には可能ですが、本機能は家庭内のローカルLLM利用を前提にしています。

設定後は `ANALYZE NOW` で手動報告を確認してから定期分析を有効にしてください。NetPulseは指定期間の監視サンプルを平均・最小・最大へ集約し、到達性、イベント、端末・エージェント状態とともにLLMへ渡します。パケット本文、閲覧URL、保存済みAPIキーはプロンプトに含めません。報告はSQLiteへ保存され、画面の履歴から参照できます。

`星図に引用する報告` では、NETWORK CONSTELLATION右上の薄いLLMテキストフィードへ流す範囲を `直近3回分`、`直近5回分`、`直近10回分`、`直近24時間分` から選べます。古い報告からタイプライター表示し、内容が表示枠を超えると末尾へ自動スクロールします。OSの「視差効果を減らす／アニメーションを減らす」が有効な場合は全文の静止表示になります。

APIキーは通常のLM Studioでは不要です。入力した場合もAPIレスポンスへ値を返さず、`data/.llm-settings.key` のローカル鍵で暗号化してSQLiteへ保存します。Base URLを別の接続先へ変更したときは、意図しない転送を防ぐため保存済みAPIキーを自動的に解除します。バックアップ時は `netpulse.db` と `.llm-settings.key` を一緒に保管し、どちらも公開リポジトリへ入れないでください。LLM設定はSQLiteが実行時の正本となり、画面で保存した変更は次の分析から即時反映されます。

## SNMPを有効にする

QNAP TS-464ではQTSのSNMPサービスを有効にし、SNMP v3、認証、プライバシーを有効にします。QTS側でAESを選択できない場合はCBC-DESを選び、NetPulse側を`SNMP_PRIV_PROTOCOL=DES`にします。認証方式もQTS表示に合わせ、HMAC-MD5なら`MD5`、SHAなら`SHA`を指定してください。

`.env`の設定例です。IP、ユーザー名、パスワードは実際の値へ置き換え、値をGitやチャットへ貼らないでください。

```dotenv
SNMP_ENABLED=true
SNMP_TARGETS=192.168.10.20
SNMP_VERSION=3
SNMP_PROFILE=qnap
SNMP_USERNAME=netpulse
SNMP_AUTH_PROTOCOL=MD5
SNMP_AUTH_PASSWORD=ここにQTS側と同じ認証パスワード
SNMP_PRIV_PROTOCOL=DES
SNMP_PRIV_PASSWORD=ここにQTS側と同じプライバシーパスワード
SNMP_INTERVAL_SECONDS=30
```

設定後に`docker compose up -d --build`でコンテナを再作成します。Web画面の`QNAP SNMP`カード、`/api/v1/snmp`、`/metrics`へ反映されます。CBC-DESとHMAC-MD5は古い方式なので、UDP 161をインターネットへ公開せず、信頼できる家庭内LANだけで使用してください。将来QTS側でAESまたはSHAを選べるようになった場合は、QTSとNetPulseを同時に強い方式へ変更してください。

SNMPv3のユーザー名とパスワードは環境変数からのみ読み込み、API、Web画面、Prometheusラベル、イベントへ出力しません。QNAP MIBは対応可能な項目の定義なので、TS-464の構成によって存在しない表や値は表示されないことがあります。

ルーター向けの従来収集を使う場合は`SNMP_VERSION=2c`、`SNMP_PROFILE=generic`、`SNMP_COMMUNITY`、`SNMP_INTERFACE_INDEX`を設定します。QNAP自身の詳細監視にはOpenWrtは必要ありません。

## Prometheus exporterを利用する

Linuxにはnode_exporter、Windowsにはwindows_exporterを導入し、それぞれの待受ポートをRaspberry Pi `192.168.10.201` からだけアクセスできるようホスト側ファイアウォールで制限します。インターネットやLAN全体へ無制限に公開しないでください。

`.env` の設定例:

```dotenv
PROMETHEUS_EXPORTERS_ENABLED=true
PROMETHEUS_EXPORTER_TARGETS=linux-nas=http://192.168.10.20:9100/metrics,windows-pc=http://192.168.10.30:9182/metrics
PROMETHEUS_EXPORTER_INTERVAL_SECONDS=15
```

NetPulseはPrometheusテキスト形式を直接読み取るため、別のPrometheusサーバーは必須ではありません。対象URLはLAN内・ループバック・リンクローカルへ解決されるアドレスだけを許可し、リダイレクト、URL埋め込み認証情報、クエリ文字列を拒否します。対応対象はnode_exporterとwindows_exporterです。取得したホスト指標はWeb画面、`/api/v1/exporters`、LLM報告、NetPulse自身の`/metrics`へ統合されます。

既存のNetPulse Agentと併用できます。同じ端末をAgentとexporterの両方で登録すると別ノードとして表示されるため、通常はどちらか一方を選んでください。AgentはPrometheus exporterをまだ導入していない端末での簡単な導入方法として残しています。

## LAN内サービスを監視する

ルーター、NAS、DNS、Web UIなど、Raspberry Piから到達できるLAN内サービスを低頻度で確認できます。対象は`.env`へカンマ区切りで設定します。

```dotenv
LAN_PROBE_TARGETS=gateway=icmp://192.168.10.1,nas-smb=tcp://192.168.10.20:445,nas-web=http://192.168.10.20:5000/health
```

ICMPは応答時間、TCPは接続確立、HTTP(S)は200〜399応答を正常と判定します。対象ホストはLAN内・ループバック・リンクローカルへ解決されるアドレスだけを許可し、HTTPリダイレクトは追跡しません。パケット本文や閲覧内容は取得・保存しません。

インターネット側の監視は既定で無効です。従来の外部ICMPとDNS確認が必要な場合だけ`INTERNET_PROBES_ENABLED=true`を設定してください。

## Windows/Linuxエージェント

サーバーの `.env` に32バイト以上のランダムな `AGENT_TOKEN` を設定します。例えばRaspberry Pi上で `openssl rand -hex 32` を実行して生成できます。設定後はNetPulseを再作成してください。

画面上部の「文字サイズ」で小・中・大を選択できます。既定は読みやすさを高めた「中」で、選択内容はブラウザに保存されます。

画面の `AGENT FLEET` にある `EASY SETUP` を開き、監視端末でWindowsまたはLinuxのコマンドを管理者権限で実行します。必要ファイルはNetPulseから自動取得されるため、`agent` フォルダーのコピーや実行場所の移動は不要です。詳しい手順とオフライン用手順は [agent/README.md](agent/README.md) にあります。

登録トークンは実行時に非表示で入力し、コマンドや画面には埋め込みません。トークン本体はハートビートでも送信せず、リクエスト本文をHMAC-SHA256で署名します。

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

Windows PowerShellでは有効化コマンドを `.\.venv\Scripts\Activate.ps1` に読み替えてください。デモ表示は `DEMO_MODE=true` と `DATA_DIR=./data` を設定して `uvicorn app.main:app --reload --port 39080` を実行します。

API仕様は `/docs` で確認できます。主要エンドポイントは `/api/v1/snapshot`、`/api/v1/history`、`/api/v1/traffic`、`/api/v1/connectivity`、`/api/v1/snmp`、`/api/v1/exporters`、`/api/v1/agents`、`/api/v1/events`、`/api/v1/llm/settings`、`/api/v1/llm/models`、`/api/v1/llm/reports`、`/api/v1/llm/flavor-reports`、`/ws/live` です。

## セキュリティ上の注意

このアプリは信頼できる家庭内LANでの利用を想定し、ログイン機能は持っていません。ルーターのポート転送などでインターネットへ直接公開しないでください。外部から見る場合は、VPN（WireGuard/Tailscaleなど）経由にするか、認証付きリバースプロキシを前段に置いてください。
