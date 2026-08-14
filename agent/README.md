# NetPulse Agent

Windows/Linux端末自身のCPU、メモリ、ディスク、温度、1分負荷、プロセス数、通信量、稼働時間、INETソケット数（総数・確立済み・待受）をNetPulseへ送ります。接続先アドレス、ポート一覧、通信内容は送信しません。送信内容は共有トークンによるHMAC-SHA256署名付きで、トークン自体はネットワークへ送信されません。

## かんたんインストール

NetPulseの画面で `AGENT FLEET` の `EASY SETUP` を開くと、その画面を開いているアドレスに合わせたコマンドをコピーできます。インストール中に登録トークンを1回入力するだけで、必要ファイルの取得と常駐登録まで行います。

### Linux

```bash
curl -fsSL 'http://192.168.10.201:39080/agent/install-linux.sh' -o /tmp/netpulse-install.sh && sudo sh /tmp/netpulse-install.sh 'http://192.168.10.201:39080'
```

`python3` または `venv` が不足している場合、対応するパッケージマネージャーから自動的に導入します。systemdが必要です。確認コマンドは `systemctl status netpulse-agent --no-pager` です。

### Windows

管理者PowerShellで実行します。

```powershell
$u='http://192.168.10.201:39080'; $p=Join-Path $env:TEMP 'netpulse-install.ps1'; Invoke-WebRequest "$u/agent/install-windows.ps1" -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Server $u
```

WindowsはPython 3が必要です。`python` または `py` コマンドを自動検出します。確認コマンドは `Get-ScheduledTask -TaskName NetPulseAgent` です。

## オフラインでインストール

監視端末からNetPulseの配布URLへアクセスできない場合だけ、この `agent` フォルダー全体を端末へコピーし、従来どおり `install-windows.ps1` または `install-linux.sh` を実行できます。

インストーラーが要求する登録トークンには、NetPulseサーバーの `.env` にある `AGENT_TOKEN` を入力します。トークンはチャット、Git、画面へ貼らないでください。

HTTP利用時もトークン本体は送信しませんが、インストーラーとメトリクスは暗号化されません。信頼できるLAN内だけで使い、信頼できないネットワークを経由する場合はHTTPSまたはVPNを使用してください。
