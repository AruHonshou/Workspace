[CmdletBinding()]
param([string]$ManifestPath)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $ManifestPath) { $ManifestPath = Join-Path $repoRoot 'assets\manifest.json' }
$ManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)
$errors = [System.Collections.Generic.List[string]]::new()
$repoPrefix = $repoRoot.TrimEnd('\') + '\'

function Add-ValidationError { param([string]$Message) $script:errors.Add($Message) }

function Resolve-AssetFile {
    param([string]$RelativePath)
    $resolved = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RelativePath.Replace('/', '\')))
    if (-not $resolved.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-ValidationError "Asset path escapes the repository: $RelativePath"
        return $null
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        Add-ValidationError "Asset is missing: $RelativePath"
        return $null
    }
    $assetFile = Get-Item -LiteralPath $resolved
    if (($assetFile.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        Add-ValidationError "Asset must not be a reparse point: $RelativePath"
        return $null
    }
    return $resolved
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Asset manifest not found: $ManifestPath" }
try { $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json }
catch { throw "Asset manifest is not valid JSON: $($_.Exception.Message)" }

if ($manifest.schema_version -ne '2.0') { Add-ValidationError 'schema_version must be 2.0.' }
if ($manifest.policy.default_renderer -ne 'procedural_scene_with_static_fallback') { Add-ValidationError 'The renderer must use the procedural workspace scene.' }
if ($manifest.policy.public_browser_delivery_is_redistribution -ne $true) { Add-ValidationError 'Browser delivery must remain recorded as redistribution.' }
if ($manifest.policy.external_visual_or_audio_assets -ne $false) { Add-ValidationError 'The workspace must not depend on external visual or audio assets.' }
if ($manifest.scene.scene_id -ne 'professional_workspace' -or $manifest.scene.kind -ne 'procedural_geometry') { Add-ValidationError 'Unexpected workspace scene metadata.' }
if ($manifest.scene.source_path -ne 'frontend/src/components/DeskScene.tsx') { Add-ValidationError 'Unexpected workspace scene source.' }
if ([string]::IsNullOrWhiteSpace([string]$manifest.scene.provenance)) { Add-ValidationError 'Scene provenance is missing.' }
$scenePath = Resolve-AssetFile ([string]$manifest.scene.source_path)
if ($scenePath) {
    $sceneSource = Get-Content -LiteralPath $scenePath -Raw -Encoding UTF8
    if ($sceneSource -match 'GLTFLoader|TextureLoader|/models/') { Add-ValidationError 'The workspace scene must not load an external model or texture.' }
}

$expectedAssets = @{
    workspace_mark = @{ Path = 'frontend/public/branding/workspace-mark.svg'; RuntimeUri = '/branding/workspace-mark.svg' }
    desk_fallback = @{ Path = 'frontend/public/branding/desk-fallback.svg'; RuntimeUri = '/branding/desk-fallback.svg' }
}
$seen = @{}
$supportingAssets = @($manifest.supporting_assets)
if ($supportingAssets.Count -ne 2) { Add-ValidationError 'Expected the neutral mark and static desk fallback.' }
foreach ($asset in $supportingAssets) {
    $assetId = [string]$asset.asset_id
    if (-not $expectedAssets.ContainsKey($assetId)) { Add-ValidationError "Unexpected asset: $assetId"; continue }
    if ($seen.ContainsKey($assetId)) { Add-ValidationError "Duplicate asset: $assetId"; continue }
    $seen[$assetId] = $true
    $expected = $expectedAssets[$assetId]
    if ($asset.path -ne $expected.Path -or $asset.runtime_uri -ne $expected.RuntimeUri -or $asset.kind -ne 'image' -or $asset.format -ne 'svg') {
        Add-ValidationError "Unexpected metadata for $assetId."
    }
    if ([string]::IsNullOrWhiteSpace([string]$asset.provenance)) { Add-ValidationError "Missing provenance: $assetId" }
    $assetPath = Resolve-AssetFile ([string]$asset.path)
    if (-not $assetPath) { continue }
    $svgSource = Get-Content -LiteralPath $assetPath -Raw -Encoding UTF8
    try {
        $settings = [System.Xml.XmlReaderSettings]::new()
        $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
        $settings.XmlResolver = $null
        $reader = [System.Xml.XmlReader]::Create([System.IO.StringReader]::new($svgSource), $settings)
        try {
            $svg = [System.Xml.XmlDocument]::new()
            $svg.XmlResolver = $null
            $svg.Load($reader)
        } finally { $reader.Dispose() }
        if ($svg.DocumentElement.LocalName -ne 'svg' -or $svg.DocumentElement.NamespaceURI -ne 'http://www.w3.org/2000/svg' -or -not $svg.DocumentElement.HasAttribute('viewBox')) {
            Add-ValidationError "Asset must be an SVG with a viewBox: $assetId"
        }
    } catch { Add-ValidationError "Invalid SVG: $assetId" }
    if ($svgSource -match '<(?:script|foreignObject|image|audio|video)\b|\son[a-z]+\s*=|(?:href|src)\s*=\s*["''][^#"''\s]|url\(\s*["'']?[^#"'')\s]') {
        Add-ValidationError "SVG must contain only local static artwork: $assetId"
    }
}
foreach ($assetId in $expectedAssets.Keys) {
    if (-not $seen.ContainsKey($assetId)) { Add-ValidationError "Required asset is absent: $assetId" }
}

$publicDir = Join-Path $repoRoot 'frontend\public'
foreach ($file in Get-ChildItem -LiteralPath $publicDir -File -Recurse) {
    if ($file.Extension -match '^\.(glb|gltf|mp3|wav|ogg|m4a|flac)$' -or $file.Name -in @('ame.png', 'ame-terrarium-poster.svg')) {
        Add-ValidationError "Retired model, character image or audio still ships: $($file.Name)"
    }
}
$html = Get-Content -LiteralPath (Join-Path $repoRoot 'frontend\index.html') -Raw -Encoding UTF8
if ($html -notmatch 'href="/branding/workspace-mark.svg"') { Add-ValidationError 'The browser icon must use the local workspace SVG.' }
if ($html -match '(?:src|href)\s*=\s*["'']https?://') { Add-ValidationError 'The HTML must not load remote resources.' }
$schemaPath = Join-Path (Split-Path -Parent $ManifestPath) 'manifest.schema.json'
if (-not (Test-Path -LiteralPath $schemaPath -PathType Leaf)) { Add-ValidationError 'Manifest schema is missing.' }
else {
    try { $null = Get-Content -LiteralPath $schemaPath -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { Add-ValidationError 'Manifest schema is not valid JSON.' }
}

if ($errors.Count -gt 0) {
    Write-Host "Asset validation failed with $($errors.Count) error(s):" -ForegroundColor Red
    foreach ($validationError in $errors) { Write-Host "  - $validationError" -ForegroundColor Red }
    exit 1
}
Write-Host 'Asset validation passed: procedural scene, local SVGs, and no retired model or soundtrack.' -ForegroundColor Green
