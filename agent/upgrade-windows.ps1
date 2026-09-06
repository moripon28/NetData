[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$TaskName = "NetPulseAgent"
$InstallDir = Join-Path $env:ProgramData "NetPulseAgent"
$AgentScript = Join-Path $InstallDir "netpulse_agent.py"
$DownloadDir = Join-Path ([IO.Path]::GetTempPath()) ("netpulse-agent-up-" + [guid]::NewGuid().ToString("N"))

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this updater from PowerShell opened with 'Run as administrator'."
    }
}

function Get-ServerFromTask {
    param([string]$TaskName)
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $task) { throw "The NetPulseAgent scheduled task was not found. Install the agent first (install-windows.ps1)." }
    $arguments = $task.Actions.Arguments
    if ([string]::IsNullOrWhiteSpace($arguments)) { throw "The NetPulseAgent scheduled task has no arguments. Install the agent first." }
    $matches = [regex]::Matches($arguments, '--server\s+\"([^\"]+)\"')
    if ($matches.Count -eq 0) { throw "Could not find the server URL in the NetPulseAgent task arguments." }
    return $matches[0].Groups[1].Value.TrimEnd("/")
}

function Get-AgentVersion {
    param([string]$Path)
    $line = Select-String -LiteralPath $Path -Pattern '^VERSION = "([^"]+)"' | Select-Object -First 1
    if ($null -eq $line) { throw "The file does not look like a NetPulse agent (VERSION line missing)." }
    return $line.Matches[0].Groups[1].Value
}

try {
    Assert-Administrator
    if (-not (Test-Path -LiteralPath $AgentScript)) {
        throw "The agent script is missing at $AgentScript. Install the agent first (install-windows.ps1)."
    }
    $Server = Get-ServerFromTask -TaskName $TaskName
    Write-Host "Downloading the NetPulse agent from $Server ..."
    New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
    $newFile = Join-Path $DownloadDir "netpulse_agent.py"
    Invoke-WebRequest -Uri "$Server/agent/netpulse_agent.py" -OutFile $newFile -TimeoutSec 20

    $newVersion = Get-AgentVersion -Path $newFile
    $oldVersion = Get-AgentVersion -Path $AgentScript
    if ($newVersion -eq $oldVersion) {
        Write-Host "The agent is already at version $newVersion. Nothing to do."
        exit 0
    }

    $backup = "$AgentScript.bak"
    Copy-Item -LiteralPath $AgentScript -Destination $backup -Force
    try {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        Copy-Item -LiteralPath $newFile -Destination $AgentScript -Force
        Start-ScheduledTask -TaskName $TaskName
    } catch {
        Copy-Item -LiteralPath $backup -Destination $AgentScript -Force
        Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        throw
    }
    Write-Host "NetPulse agent upgraded: $oldVersion -> $newVersion" -ForegroundColor Green
    Write-Host "Verify: Get-ScheduledTask -TaskName NetPulseAgent"
} finally {
    if (Test-Path -LiteralPath $DownloadDir) {
        Remove-Item -LiteralPath $DownloadDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
