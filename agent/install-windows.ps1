[CmdletBinding()]
param(
    [string]$Server = "http://192.168.10.201:39080"
)

$ErrorActionPreference = "Stop"
$InstallDir = Join-Path $env:ProgramData "NetPulseAgent"
$DownloadDir = Join-Path ([IO.Path]::GetTempPath()) ("netpulse-agent-" + [guid]::NewGuid().ToString("N"))
$PayloadDir = $null

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this installer from PowerShell opened with 'Run as administrator'."
    }
}

function Resolve-Python {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        return [pscustomobject]@{ Executable = $launcher.Source; Prefix = @("-3") }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike "*\WindowsApps\python*.exe") {
        return [pscustomobject]@{ Executable = $python.Source; Prefix = @() }
    }

    throw "Python 3 was not found. Install it from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH', then run this command again."
}

function Invoke-CheckedCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

function Download-AgentPayload {
    param([string]$SourceBase)

    New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
    foreach ($name in @("netpulse_agent.py", "requirements.txt")) {
        Invoke-WebRequest -Uri "$SourceBase/$name" -OutFile (Join-Path $DownloadDir $name) -TimeoutSec 20
    }
    return $DownloadDir
}

Assert-Administrator

$serverUri = $null
if (-not [Uri]::TryCreate($Server, [UriKind]::Absolute, [ref]$serverUri) -or $serverUri.Scheme -notin @("http", "https")) {
    throw "Server must be an http:// or https:// URL."
}
$Server = $Server.TrimEnd("/")

try {
    Write-Host "Downloading the NetPulse agent from $Server ..."
    try {
        $PayloadDir = Download-AgentPayload -SourceBase "$Server/agent"
    } catch {
        $localAgent = Join-Path $PSScriptRoot "netpulse_agent.py"
        $localRequirements = Join-Path $PSScriptRoot "requirements.txt"
        if ((Test-Path -LiteralPath $localAgent) -and (Test-Path -LiteralPath $localRequirements)) {
            Write-Warning "The server download was unavailable. Using the files next to this installer."
            $PayloadDir = $PSScriptRoot
        } else {
            throw "Could not download the agent files from $Server. Check that NetPulse is running and reachable. $($_.Exception.Message)"
        }
    }

    $Python = Resolve-Python
    $PythonExecutable = $Python.Executable
    $PythonPrefix = @($Python.Prefix)
    Invoke-CheckedCommand -Executable $PythonExecutable -Arguments ($PythonPrefix + @("--version"))

    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PayloadDir "netpulse_agent.py") -Destination $InstallDir -Force

    $VenvDir = Join-Path $InstallDir "venv"
    Invoke-CheckedCommand -Executable $PythonExecutable -Arguments ($PythonPrefix + @("-m", "venv", $VenvDir))
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    Invoke-CheckedCommand -Executable $VenvPython -Arguments @(
        "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "-r",
        (Join-Path $PayloadDir "requirements.txt")
    )

    $SecureToken = Read-Host "NetPulse agent enrollment token" -AsSecureString
    $TokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
    try {
        $Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($TokenPtr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($TokenPtr)
    }
    if ([string]::IsNullOrWhiteSpace($Token) -or $Token.Length -lt 32) {
        throw "The enrollment token must contain at least 32 characters."
    }

    $TokenFile = Join-Path $InstallDir "agent.token"
    [IO.File]::WriteAllText($TokenFile, $Token, [Text.UTF8Encoding]::new($false))
    $Token = $null
    $Acl = Get-Acl $TokenFile
    $Acl.SetAccessRuleProtection($true, $false)
    $SystemSid = [Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $AdminSid = [Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $Acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($SystemSid, "FullControl", "Allow"))
    $Acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($AdminSid, "FullControl", "Allow"))
    Set-Acl -LiteralPath $TokenFile -AclObject $Acl

    $AgentScript = Join-Path $InstallDir "netpulse_agent.py"
    $Action = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$AgentScript`" --server `"$Server`" --token-file `"$TokenFile`""
    $Trigger = New-ScheduledTaskTrigger -AtStartup
    $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $Settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName "NetPulseAgent" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
    Start-ScheduledTask -TaskName "NetPulseAgent"

    Write-Host "NetPulse agent installed and started." -ForegroundColor Green
    Write-Host "Dashboard: $Server"
    Write-Host "Verify: Get-ScheduledTask -TaskName NetPulseAgent"
} finally {
    if (Test-Path -LiteralPath $DownloadDir) {
        Remove-Item -LiteralPath $DownloadDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
