[CmdletBinding()]
param(
    [switch]$Quick,
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Assert-LastExitCode {
    param([string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

Write-Host 'Validating public asset boundary...' -ForegroundColor Cyan
& (Join-Path $PSScriptRoot 'validate-assets.ps1')
if (-not $?) {
    throw 'Asset validation failed.'
}

if (-not $SkipBackend) {
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw 'Python virtual environment missing. Run ./scripts/bootstrap.ps1 first.'
    }
    $pytestTempRoot = Join-Path $repoRoot 'tmp'
    New-Item -ItemType Directory -Force -Path $pytestTempRoot | Out-Null
    $pytestTemp = Join-Path $pytestTempRoot ("pytest-" + [System.Guid]::NewGuid().ToString('N'))
    Write-Host 'Running backend tests...' -ForegroundColor Cyan
    & $venvPython -m pytest (Join-Path $repoRoot 'backend') --basetemp $pytestTemp -p no:cacheprovider
    Assert-LastExitCode 'Backend tests'

    if (-not $Quick) {
        Push-Location (Join-Path $repoRoot 'backend')
        try {
            & $venvPython -m ruff check .
            Assert-LastExitCode 'Backend lint'
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipFrontend) {
    $pnpm = Get-Command pnpm -ErrorAction Stop | Select-Object -First 1
    Push-Location $repoRoot
    try {
        Write-Host 'Running frontend tests...' -ForegroundColor Cyan
        & $pnpm.Source test
        Assert-LastExitCode 'Frontend tests'

        & $pnpm.Source typecheck
        Assert-LastExitCode 'Frontend typecheck'

        if (-not $Quick) {
            & $pnpm.Source lint
            Assert-LastExitCode 'Frontend lint'
            & $pnpm.Source build
            Assert-LastExitCode 'Frontend build'
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host 'All selected checks passed.' -ForegroundColor Green
