[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$git = Get-Command git -ErrorAction Stop | Select-Object -First 1

Push-Location $repoRoot
try {
    $files = @(& $git.Source ls-files --cached --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to enumerate repository files.' }

    $excluded = @(
        'pnpm-lock.yaml', 'backend/uv.lock', 'scripts/scan-secrets.ps1'
    )
    $binaryExtensions = @(
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.glb', '.mp3',
        '.pdf', '.woff', '.woff2', '.ttf', '.zip'
    )
    $patterns = @(
        '(?i)\beyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\b',
        '(?i)\b(?:sk|jp_live|ts_live)_[a-zA-Z0-9_-]{20,}\b',
        '(?i)\b(?:DEEPSEEK|THEIRSTACK)_API_KEY\s*=\s*[^\s$][^\r\n]{11,}'
    )
    $findings = New-Object System.Collections.Generic.List[string]

    foreach ($relative in $files) {
        $normalized = $relative.Replace('\', '/')
        if ($excluded -contains $normalized) { continue }
        $extension = [System.IO.Path]::GetExtension($normalized).ToLowerInvariant()
        if ($binaryExtensions -contains $extension) { continue }
        $absolute = Join-Path $repoRoot $relative
        if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) { continue }
        try { $content = Get-Content -LiteralPath $absolute -Raw -Encoding utf8 }
        catch { continue }
        foreach ($pattern in $patterns) {
            if ($content -match $pattern) {
                $findings.Add($normalized)
                break
            }
        }
    }

    if ($findings.Count -gt 0) {
        $findings | Sort-Object -Unique | ForEach-Object {
            Write-Error "Potential secret detected in tracked content: $_"
        }
        exit 1
    }
    Write-Host 'Secret scan passed.' -ForegroundColor Green
}
finally {
    Pop-Location
}
