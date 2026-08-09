# NetPulse Agent

Windows/Linux端末自身のCPU、メモリ、ディスク、温度、通信量、稼働時間をNetPulseへ送ります。送信内容は共有トークンによるHMAC-SHA256署名付きで、トークン自体はネットワークへ送信されません。

## Linux

```bash
sudo ./install-linux.sh http://192.168.10.201:8080
systemctl status netpulse-agent
```

## Windows

管理者PowerShellで実行します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows.ps1 -Server http://192.168.10.201:8080
Get-ScheduledTask NetPulseAgent
```

インストーラーが要求する登録トークンには、NetPulseサーバーの `.env` にある `AGENT_TOKEN` を入力します。トークンはチャット、Git、画面へ貼らないでください。

HTTP利用時もトークン本体は送信しませんが、メトリクスは暗号化されません。信頼できないネットワークを経由する場合はHTTPSまたはVPNを使用してください。
