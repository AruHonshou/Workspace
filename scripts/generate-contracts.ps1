[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonCandidates = @(
    (Join-Path $repoRoot '.venv\Scripts\python.exe'),
    (Join-Path $repoRoot '.venv/bin/python'),
    (Join-Path $repoRoot 'backend/.venv\Scripts\python.exe'),
    (Join-Path $repoRoot 'backend/.venv/bin/python')
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $python) { throw 'Python environment missing. Run ./scripts/bootstrap.ps1 first.' }
$pnpm = Get-Command pnpm -ErrorAction Stop | Select-Object -First 1
$generatedRoot = Join-Path $repoRoot 'frontend/src/generated'
$openapiPath = Join-Path $generatedRoot 'openapi.json'

& $python (Join-Path $PSScriptRoot 'export_openapi.py') --output $openapiPath
if ($LASTEXITCODE -ne 0) { throw 'OpenAPI export failed.' }

Push-Location (Join-Path $repoRoot 'frontend')
try {
    & $pnpm.Source exec openapi-typescript 'src/generated/openapi.json' `
        --output 'src/generated/api.d.ts'
    if ($LASTEXITCODE -ne 0) { throw 'TypeScript contract generation failed.' }
}
finally {
    Pop-Location
}
Write-Host 'OpenAPI JSON and TypeScript contracts generated.' -ForegroundColor Green
