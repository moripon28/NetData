param(
    [string]$Server = "http://192.168.10.201:39080"
)

$ErrorActionPreference = "Stop"
$InstallDir = Join-Path $env:ProgramData "NetPulseAgent"
$Python = Get-Command python -ErrorAction Stop
$SecureToken = Read-Host "NetPulse agent enrollment token" -AsSecureString
$TokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
try {
    $Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($TokenPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($TokenPtr)
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "netpulse_agent.py") -Destination $InstallDir -Force
& $Python.Source -m venv (Join-Path $InstallDir "venv")
$VenvPython = Join-Path $InstallDir "venv\Scripts\python.exe"
& $VenvPython -m pip install --no-cache-dir -r (Join-Path $PSScriptRoot "requirements.txt")

$TokenFile = Join-Path $InstallDir "agent.token"
[IO.File]::WriteAllText($TokenFile, $Token, [Text.UTF8Encoding]::new($false))
$Acl = Get-Acl $TokenFile
$Acl.SetAccessRuleProtection($true, $false)
$SystemSid = New-Object Security.Principal.SecurityIdentifier("S-1-5-18")
$AdminSid = New-Object Security.Principal.SecurityIdentifier("S-1-5-32-544")
$SystemRule = New-Object Security.AccessControl.FileSystemAccessRule($SystemSid, "FullControl", "Allow")
$AdminRule = New-Object Security.AccessControl.FileSystemAccessRule($AdminSid, "FullControl", "Allow")
$Acl.AddAccessRule($SystemRule)
$Acl.AddAccessRule($AdminRule)
Set-Acl -LiteralPath $TokenFile -AclObject $Acl

$AgentScript = Join-Path $InstallDir "netpulse_agent.py"
$Action = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$AgentScript`" --server `"$Server`" --token-file `"$TokenFile`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "NetPulseAgent" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName "NetPulseAgent"
Write-Host "NetPulse agent installed and started."
