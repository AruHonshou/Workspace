[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venvRoot = Join-Path $repoRoot '.venv'
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Assert-LastExitCode {
    param([string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

function Assert-RequiredFile {
    param(
        [string]$Path,
        [string]$Description
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description not found: $Path"
    }
}

function Get-Python312Path {
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        & $venvPython -c "import sys; assert sys.version_info[:2] == (3, 12)"
        if ($LASTEXITCODE -eq 0) {
            return [System.IO.Path]::GetFullPath($venvPython)
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($py) {
        $detected = @(& $py.Source -3.12 -c "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $detected.Count -gt 0) {
            return [System.IO.Path]::GetFullPath(([string]$detected[-1]).Trim())
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($python) {
        $detected = @(& $python.Source -c "import sys; assert sys.version_info[:2] == (3, 12); print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $detected.Count -gt 0) {
            return [System.IO.Path]::GetFullPath(([string]$detected[-1]).Trim())
        }
    }

    throw 'Python 3.12 is required and must be discoverable through py, python, or the existing root .venv.'
}

Write-Host "Workspace bootstrap: $repoRoot" -ForegroundColor Cyan

if (-not $SkipBackend) {
    $backendRoot = Join-Path $repoRoot 'backend'
    $backendProject = Join-Path $backendRoot 'pyproject.toml'
    $backendLock = Join-Path $backendRoot 'uv.lock'
    Assert-RequiredFile $backendProject 'Backend project'
    Assert-RequiredFile $backendLock 'Backend uv lockfile'

    $uv = Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $uv) {
        throw 'uv is required on PATH. Install uv, reopen PowerShell, and rerun bootstrap; the script will not fall back to an unlocked pip install.'
    }
    $python312 = Get-Python312Path

    & $uv.Source lock --project $backendRoot --check --python $python312 `
        --no-python-downloads
    Assert-LastExitCode 'Validating backend uv.lock against pyproject.toml'

    $previousProjectEnvironment = [Environment]::GetEnvironmentVariable(
        'UV_PROJECT_ENVIRONMENT',
        [EnvironmentVariableTarget]::Process
    )
    try {
        [Environment]::SetEnvironmentVariable(
            'UV_PROJECT_ENVIRONMENT',
            $venvRoot,
            [EnvironmentVariableTarget]::Process
        )
        & $uv.Source sync --project $backendRoot --locked --extra test `
            --extra ocr --python $python312 --no-python-downloads
        Assert-LastExitCode 'Synchronizing backend from the locked dependency set'
    }
    finally {
        [Environment]::SetEnvironmentVariable(
            'UV_PROJECT_ENVIRONMENT',
            $previousProjectEnvironment,
            [EnvironmentVariableTarget]::Process
        )
    }

    Assert-RequiredFile $venvPython 'Locked Python virtual environment'
    & $venvPython -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version"
    Assert-LastExitCode 'Checking locked Python 3.12 environment'
}

if (-not $SkipFrontend) {
    $rootPackagePath = Join-Path $repoRoot 'package.json'
    $frontendPackagePath = Join-Path $repoRoot 'frontend\package.json'
    $workspacePath = Join-Path $repoRoot 'pnpm-workspace.yaml'
    $pnpmLockPath = Join-Path $repoRoot 'pnpm-lock.yaml'
    Assert-RequiredFile $rootPackagePath 'Root package manifest'
    Assert-RequiredFile $frontendPackagePath 'Frontend package manifest'
    Assert-RequiredFile $workspacePath 'pnpm workspace manifest'
    Assert-RequiredFile $pnpmLockPath 'pnpm workspace lockfile'

    $workspaceText = Get-Content -LiteralPath $workspacePath -Raw
    if ($workspaceText -notmatch '(?m)^\s*-\s+frontend\s*$') {
        throw 'pnpm-workspace.yaml must include the frontend workspace.'
    }
    $lockText = Get-Content -LiteralPath $pnpmLockPath -Raw
    if ($lockText -notmatch '(?m)^  frontend:\s*$') {
        throw 'pnpm-lock.yaml does not contain the frontend workspace importer.'
    }

    $rootPackage = Get-Content -LiteralPath $rootPackagePath -Raw | ConvertFrom-Json
    $packageManager = [string]$rootPackage.packageManager
    if ($packageManager -notmatch '^pnpm@(\d+\.\d+\.\d+)$') {
        throw 'package.json must pin pnpm with packageManager: pnpm@<exact-version>.'
    }
    $expectedPnpmVersion = $Matches[1]
    $pnpm = Get-Command pnpm -ErrorAction Stop | Select-Object -First 1
    $pnpmVersionOutput = @(& $pnpm.Source --version 2>&1)
    Assert-LastExitCode 'Reading pnpm version'
    $actualPnpmVersion = [string](
        $pnpmVersionOutput |
            Where-Object { [string]$_ -match '^\d+\.\d+\.\d+$' } |
            Select-Object -Last 1
    )
    if ($actualPnpmVersion.Trim() -ne $expectedPnpmVersion) {
        throw "pnpm $expectedPnpmVersion is required by package.json; found '$($actualPnpmVersion.Trim())'."
    }

    Push-Location $repoRoot
    try {
        & $pnpm.Source install --frozen-lockfile
        Assert-LastExitCode 'Installing the locked pnpm workspace'
    }
    finally {
        Pop-Location
    }
}

& (Join-Path $PSScriptRoot 'validate-assets.ps1')
Assert-LastExitCode 'Validating assets'

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.env') -PathType Leaf)) {
    Write-Warning 'No .env file exists. Copy .env.example to .env before a live run.'
}

Write-Host 'Bootstrap completed. No 3D assets were downloaded.' -ForegroundColor Green
