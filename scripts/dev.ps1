[CmdletBinding()]
param(
    [string]$BackendApp = 'job_orchestrator.main:app',
    [switch]$AllowNonLoopback
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$children = New-Object System.Collections.Generic.List[System.Diagnostics.Process]

function Import-LocalEnvironment {
    $envPath = Join-Path $repoRoot '.env'
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        return
    }
    foreach ($line in Get-Content -LiteralPath $envPath) {
        if ($line -match '^\s*#' -or $line -notmatch '=') {
            continue
        }
        $parts = $line -split '=', 2
        $name = $parts[0].Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            continue
        }
        $value = $parts[1].Trim().Trim('"').Trim("'")
        Set-Item -Path "Env:$name" -Value $value
    }
}

function Remove-ExpiredLocalLogs {
    $logsRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'logs'))
    $repoPrefix = [System.IO.Path]::GetFullPath($repoRoot).TrimEnd('\') + '\'
    if (-not $logsRoot.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to purge logs outside the repository: $logsRoot"
    }
    if (-not (Test-Path -LiteralPath $logsRoot -PathType Container)) {
        return
    }
    $cutoff = (Get-Date).ToUniversalTime().AddDays(-30)
    Get-ChildItem -LiteralPath $logsRoot -File |
        Where-Object { $_.LastWriteTimeUtc -lt $cutoff } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
}

function Start-HiddenLoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$Name,
        [string]$Stamp
    )
    $logsRoot = Join-Path $repoRoot 'logs'
    if (-not (Test-Path -LiteralPath $logsRoot -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $logsRoot
    }
    $stdout = Join-Path $logsRoot "$Name-$Stamp.stdout.log"
    $stderr = Join-Path $logsRoot "$Name-$Stamp.stderr.log"
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $script:children.Add($process)
    Write-Host "$Name started as PID $($process.Id). Logs: $stdout and $stderr"
    return $process
}

function Assert-TcpPortAvailable {
    param([int]$Port, [string]$Service)
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $listener) {
        throw "$Service cannot start because port $Port is already used by PID $($listener.OwningProcess). Stop the previous development process first."
    }
}

function Resolve-NodePath {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($nodeCommand -and (Test-Path -LiteralPath $nodeCommand.Source -PathType Leaf)) {
        return [System.IO.Path]::GetFullPath($nodeCommand.Source)
    }

    # Some managed development environments expose pnpm through a wrapper while
    # keeping the Node runtime outside PATH. Search only well-known locations and
    # the pnpm wrapper's nearby runtime folders; do not recursively scan the disk.
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:NODE_HOME) {
        $candidates.Add((Join-Path $env:NODE_HOME 'node.exe'))
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles 'nodejs\node.exe'))
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if ($programFilesX86) {
        $candidates.Add((Join-Path $programFilesX86 'nodejs\node.exe'))
    }
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\nodejs\node.exe'))
    }

    $pnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($pnpmCommand -and $pnpmCommand.Source) {
        $searchRoot = Split-Path -Parent $pnpmCommand.Source
        for ($level = 0; $level -lt 5 -and $searchRoot; $level++) {
            $candidates.Add((Join-Path $searchRoot 'node.exe'))
            $candidates.Add((Join-Path $searchRoot 'bin\node.exe'))
            $candidates.Add((Join-Path $searchRoot 'node\bin\node.exe'))
            $parent = Split-Path -Parent $searchRoot
            if (-not $parent -or $parent -eq $searchRoot) {
                break
            }
            $searchRoot = $parent
        }
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }

    throw 'Node.js 22 or newer was not found. Install Node.js, reopen PowerShell, or expose NODE_HOME before running dev.ps1.'
}

function Stop-LocalProcessTree {
    param([System.Diagnostics.Process]$Process)
    if ($Process.HasExited) {
        return
    }
    if ($PSVersionTable.Platform -eq 'Win32NT') {
        & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
    }
    else {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}

Import-LocalEnvironment
Remove-ExpiredLocalLogs

$hostName = if ($env:JOB_ORCHESTRATOR_HOST) { $env:JOB_ORCHESTRATOR_HOST } else { '127.0.0.1' }
$apiPort = if ($env:JOB_ORCHESTRATOR_PORT) { $env:JOB_ORCHESTRATOR_PORT } else { '8765' }
$uiPort = '5173'
if ($hostName -notin @('127.0.0.1', 'localhost', '::1') -and -not $AllowNonLoopback) {
    throw "Refusing non-loopback API host '$hostName'. Use -AllowNonLoopback only after reviewing the threat model."
}
if ($apiPort -notmatch '^\d{1,5}$' -or [int]$apiPort -lt 1 -or [int]$apiPort -gt 65535) {
    throw "Invalid JOB_ORCHESTRATOR_PORT: $apiPort"
}
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw 'Python virtual environment missing. Run ./scripts/bootstrap.ps1 first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'frontend\package.json') -PathType Leaf)) {
    throw 'frontend/package.json was not found.'
}

Assert-TcpPortAvailable -Port ([int]$apiPort) -Service 'Backend'
Assert-TcpPortAvailable -Port ([int]$uiPort) -Service 'Frontend'

& (Join-Path $PSScriptRoot 'validate-assets.ps1')
if (-not $?) {
    throw 'Asset validation failed.'
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
try {
    $backendArgs = @(
        '-m', 'uvicorn', $BackendApp,
        '--app-dir', (Join-Path $repoRoot 'backend'),
        '--host', $hostName,
        '--port', $apiPort,
        '--reload-dir', (Join-Path $repoRoot 'backend\job_orchestrator'),
        '--reload'
    )
    $backend = Start-HiddenLoggedProcess $venvPython $backendArgs 'backend' $stamp

    $nodePath = Resolve-NodePath
    $nodeVersion = @(& $nodePath --version 2>&1)
    if ($LASTEXITCODE -ne 0 -or -not ($nodeVersion[-1] -match '^v(?<major>\d+)\.')) {
        throw "Unable to read the Node.js version from '$nodePath'."
    }
    if ([int]$Matches.major -lt 22) {
        throw "Node.js 22 or newer is required; found '$($nodeVersion[-1])' at '$nodePath'."
    }
    $viteEntry = Join-Path $repoRoot 'frontend\node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $viteEntry -PathType Leaf)) {
        throw 'Vite is not installed. Run ./scripts/bootstrap.ps1 first.'
    }
    $frontendRoot = Join-Path $repoRoot 'frontend'
    $frontendArgs = @(
        $viteEntry,
        $frontendRoot,
        '--host', '127.0.0.1',
        '--port', $uiPort
    )
    $frontend = Start-HiddenLoggedProcess $nodePath $frontendArgs 'frontend' $stamp

    Write-Host ''
    Write-Host "API:      http://${hostName}:$apiPort" -ForegroundColor Cyan
    Write-Host "Frontend: http://127.0.0.1:$uiPort" -ForegroundColor Cyan
    Write-Host 'Press Ctrl+C to stop only the child processes started by this script.'

    while ($true) {
        Start-Sleep -Seconds 1
        foreach ($child in @($children)) {
            if ($child.HasExited) {
                throw "A development process exited early with code $($child.ExitCode). Check logs/."
            }
        }
    }
}
finally {
    foreach ($child in @($children)) {
        Stop-LocalProcessTree $child
        $child.Dispose()
    }
}
