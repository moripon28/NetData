[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$TaskName = "NetPulseAgent"
$InstallDir = Join-Path $env:ProgramData "NetPulseAgent"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this uninstaller from PowerShell opened with 'Run as administrator'."
    }
}

Assert-Administrator

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task: $TaskName"
} else {
    Write-Host "Scheduled task was already absent: $TaskName"
}

if (Test-Path -LiteralPath $InstallDir) {
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $InstallDir -Recurse -Force
            break
        } catch {
            if ($attempt -eq 5) { throw }
            Start-Sleep -Seconds 1
        }
    }
    Write-Host "Removed agent files: $InstallDir"
} else {
    Write-Host "Agent files were already absent: $InstallDir"
}

Write-Host "NetPulse agent uninstalled." -ForegroundColor Green
Write-Host "The saved server-side device record is unchanged. Remove it from AGENT FLEET > MANAGE if it is no longer needed."
