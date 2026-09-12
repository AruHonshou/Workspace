[CmdletBinding()]
param(
    [string]$OutputPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonCandidates = @(
    (Join-Path $repoRoot '.venv\Scripts\python.exe'),
    (Join-Path $repoRoot '.venv/bin/python'),
    (Join-Path $repoRoot 'backend/.venv\Scripts\python.exe'),
    (Join-Path $repoRoot 'backend/.venv/bin/python')
)
$venvPython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $OutputPath) {
    $OutputPath = Join-Path $repoRoot 'output/sbom/amework-global.cdx.json'
}
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput
if (-not $venvPython) {
    throw 'Python virtual environment missing. Run ./scripts/bootstrap.ps1 first.'
}
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    $null = New-Item -ItemType Directory -Path $outputDirectory
}

$components = New-Object System.Collections.Generic.List[object]
$seen = @{}
function Add-Component {
    param([string]$Type, [string]$Name, [string]$Version, [string]$Purl)
    if (-not $Name -or -not $Version) { return }
    $key = "$Type|$Name|$Version"
    if ($script:seen.ContainsKey($key)) { return }
    $script:seen[$key] = $true
    $script:components.Add([ordered]@{
        type = $Type
        name = $Name
        version = $Version
        purl = $Purl
    })
}

$uv = Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $uv) {
    $localUv = Join-Path $repoRoot '.venv\Scripts\uv.exe'
    if (Test-Path -LiteralPath $localUv -PathType Leaf) {
        $uv = Get-Item -LiteralPath $localUv
    }
}
if ($uv) {
    $uvExecutable = if ($uv.PSObject.Properties['Source']) { $uv.Source } else { $uv.FullName }
    $pythonInventory = @(& $uvExecutable pip list --python $venvPython --format=json) -join "`n"
} else {
    $pythonInventory = @(& $venvPython -m pip list --format=json) -join "`n"
}
if ($LASTEXITCODE -ne 0) { throw 'Python dependency inventory failed.' }
$pythonPackages = ($pythonInventory | ConvertFrom-Json)
foreach ($package in $pythonPackages) {
    $name = [string]$package.name
    $version = [string]$package.version
    Add-Component 'library' $name $version "pkg:pypi/$($name.ToLowerInvariant())@$version"
}

$pnpm = Get-Command pnpm -ErrorAction Stop | Select-Object -First 1
$frontendTree = @(& $pnpm.Source --dir (Join-Path $repoRoot 'frontend') list --json --depth Infinity 2>$null) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'pnpm dependency inventory failed.' }
$parsedTree = $frontendTree | ConvertFrom-Json
function Add-NpmTree {
    param([object]$Node)
    foreach ($propertyName in @('dependencies', 'devDependencies', 'optionalDependencies')) {
        $nodeProperty = $Node.psobject.Properties[$propertyName]
        if (-not $nodeProperty) { continue }
        $property = $nodeProperty.Value
        if (-not $property) { continue }
        foreach ($entry in $property.psobject.Properties) {
            $name = [string]$entry.Name
            $dependency = $entry.Value
            $version = [string]$dependency.version
            if ($version) {
                $encodedName = $name.Replace('@', '%40')
                Add-Component 'library' $name $version "pkg:npm/$encodedName@$version"
            }
            Add-NpmTree $dependency
        }
    }
}
foreach ($root in @($parsedTree)) { Add-NpmTree $root }

$bom = [ordered]@{
    bomFormat = 'CycloneDX'
    specVersion = '1.6'
    serialNumber = "urn:uuid:$([guid]::NewGuid())"
    version = 1
    metadata = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        component = [ordered]@{
            type = 'application'
            name = 'amework-global'
            version = '0.1.0'
        }
    }
    components = @($components | Sort-Object name, version)
}
$bom | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $resolvedOutput -Encoding utf8
Write-Host "CycloneDX SBOM written to $resolvedOutput" -ForegroundColor Green
