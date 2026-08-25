[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Continue'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param(
        [string]$Check,
        [string]$Status,
        [string]$Detail
    )
    $script:results.Add([pscustomobject]@{
        check = $Check
        status = $Status
        detail = $Detail
    })
}

function Get-CommandVersion {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) {
        Add-Result $Name 'missing' 'Not found on PATH.'
        return
    }
    try {
        $output = @(& $command.Source @Arguments 2>&1)
        $firstLine = [string]($output | Select-Object -First 1)
        if ([string]::IsNullOrWhiteSpace($firstLine)) {
            $firstLine = $command.Source
        }
        Add-Result $Name 'ok' $firstLine.Trim()
    }
    catch {
        Add-Result $Name 'warning' "Found at $($command.Source), but version check failed."
    }
}

Add-Result 'PowerShell' 'ok' "$($PSVersionTable.PSEdition) $($PSVersionTable.PSVersion)"
try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    Add-Result 'Windows' 'ok' "$($os.Caption) build $($os.BuildNumber)"
}
catch {
    Add-Result 'Windows' 'warning' 'Could not read operating-system details.'
}

Get-CommandVersion 'git' @('--version')
Get-CommandVersion 'python' @('--version')
Get-CommandVersion 'uv' @('--version')
Get-CommandVersion 'node' @('--version')
Get-CommandVersion 'pnpm' @('--version')

try {
    $gpus = @(Get-CimInstance Win32_VideoController -ErrorAction Stop)
    if ($gpus.Count -eq 0) {
        Add-Result 'GPU' 'warning' 'No display adapter was reported by Windows.'
    }
    foreach ($gpu in $gpus) {
        Add-Result 'GPU' 'info' "$($gpu.Name); driver $($gpu.DriverVersion)"
    }
}
catch {
    Add-Result 'GPU' 'warning' 'Could not query Win32_VideoController.'
}

try {
    $health = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8765/health' -Method Get -TimeoutSec 2
    Add-Result 'Career API' 'ok' "Local health endpoint returned HTTP $($health.StatusCode)."
}
catch {
    Add-Result 'Career API' 'info' 'No response on 127.0.0.1:8765; this is expected before dev.ps1 starts.'
}

$validator = Join-Path $PSScriptRoot 'validate-assets.ps1'
if (Test-Path -LiteralPath $validator -PathType Leaf) {
    $validationOutput = @(& $validator *>&1)
    if ($LASTEXITCODE -eq 0) {
        Add-Result 'Asset manifest' 'ok' 'One byte-verified CC BY 4.0 Ame terrarium GLB and static fallback validated.'
    }
    else {
        Add-Result 'Asset manifest' 'error' (($validationOutput | ForEach-Object { [string]$_ }) -join ' ')
    }
}
else {
    Add-Result 'Asset manifest' 'error' 'validate-assets.ps1 is missing.'
}

if ($Json) {
    $results | ConvertTo-Json -Depth 4
}
else {
    $results | Format-Table -AutoSize -Wrap
    Write-Host ''
    Write-Host 'This diagnostic is read-only. It does not install packages or display credentials.'
}

if (@($results | Where-Object { $_.status -eq 'error' }).Count -gt 0) {
    exit 1
}
