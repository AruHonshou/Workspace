[CmdletBinding()]
param([string]$ManifestPath)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $ManifestPath) { $ManifestPath = Join-Path $repoRoot 'assets\manifest.json' }
$ManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)
$errors = [System.Collections.Generic.List[string]]::new()

function Add-ValidationError { param([string]$Message) $script:errors.Add($Message) }

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Asset manifest not found: $ManifestPath" }
try { $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json }
catch { throw "Asset manifest is not valid JSON: $($_.Exception.Message)" }

if ($manifest.schema_version -ne '1.2') { Add-ValidationError 'schema_version must be 1.2.' }
if ($manifest.policy.code_license_applies_to_assets -ne $false) { Add-ValidationError 'The code license must not be applied to the third-party GLB.' }
if ($manifest.policy.public_browser_delivery_is_redistribution -ne $true) { Add-ValidationError 'Browser delivery must be treated as redistribution.' }
if ($manifest.policy.default_renderer -ne 'licensed_glb_with_static_fallback') { Add-ValidationError 'Unexpected default renderer.' }
if ($manifest.policy.use_scope -ne 'local_noncommercial_fan_project') { Add-ValidationError 'The asset use scope must stay local and noncommercial.' }

$requiredEvidence = @('author_or_rightsholder','original_source_url','license_name_and_version','license_text_or_permalink','retrieval_date','proof_of_acquisition','attribution_text','permission_to_modify','permission_to_redistribute_browser_downloadable_glb','mesh_texture_rig_animation_provenance','conversion_log','trademark_and_likeness_review')
$repoPrefix = $repoRoot.TrimEnd('\') + '\'
$slots = @($manifest.slots)

if ($slots.Count -ne 1) { Add-ValidationError "Expected exactly 1 visual-orchestrator asset; found $($slots.Count)." }
if ($slots.Count -eq 1) {
    $slot = $slots[0]
    if ($slot.slot_id -ne 'visible_orchestrator') { Add-ValidationError 'The only slot must be visible_orchestrator.' }
    if ($slot.agent_id -ne 'career_coordinator') { Add-ValidationError 'The visible model must map to career_coordinator.' }
    if ($slot.requested_identity.name -ne 'Watson Amelia') { Add-ValidationError 'Unexpected visible identity.' }
    if ($slot.requested_identity.mapping_scope -ne 'visual_orchestrator_only') { Add-ValidationError 'The model must remain a visual-only orchestrator.' }
    if ($slot.status -ne 'included_local_noncommercial' -or $slot.publishable -ne $true) { Add-ValidationError 'The documented CC BY asset must be included and publishable with attribution.' }

    $expectedRelative = 'frontend/public/models/ame-terrarium.glb'
    if ($slot.asset.path -ne $expectedRelative -or $slot.asset.runtime_uri -ne '/models/ame-terrarium.glb') { Add-ValidationError 'Unexpected GLB path or runtime URI.' }
    $resolved = [System.IO.Path]::GetFullPath((Join-Path $repoRoot ([string]$slot.asset.path).Replace('/', '\')))
    if (-not $resolved.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { Add-ValidationError 'The GLB path escapes the repository.' }
    elseif (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) { Add-ValidationError "The GLB is missing: $resolved" }
    else {
        $file = Get-Item -LiteralPath $resolved
        if (($file.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { Add-ValidationError 'The GLB must not be a reparse point.' }
        if ($file.Length -ne [long]$slot.asset.bytes) { Add-ValidationError 'The GLB byte count changed.' }
        $digest = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($digest -ne [string]$slot.asset.sha256) { Add-ValidationError 'The GLB SHA-256 changed.' }
        $header = [System.IO.File]::ReadAllBytes($resolved)[0..3]
        if ([System.Text.Encoding]::ASCII.GetString($header) -ne 'glTF') { Add-ValidationError 'The asset is not a valid GLB container.' }
    }
    if (@($slot.asset.animation_clips).Count -ne 1 -or @($slot.asset.animation_clips) -notcontains 'Animation') { Add-ValidationError 'The GLB must declare its single original Animation clip.' }
    if ([double]$slot.asset.animation_duration_seconds -ne 9.0) { Add-ValidationError 'The original animation duration must remain 9 seconds.' }

    $evidence = $slot.license_gate.evidence
    foreach ($field in $requiredEvidence) {
        if (@($slot.license_gate.required_fields) -notcontains $field) { Add-ValidationError "License evidence omits $field." }
        if ($null -eq $evidence.$field -or [string]::IsNullOrWhiteSpace([string]$evidence.$field)) { Add-ValidationError "License evidence is empty for $field." }
    }
    if ($evidence.author_or_rightsholder -ne 'Seafoam') { Add-ValidationError 'The author attribution must remain Seafoam.' }
    if ($evidence.license_name_and_version -ne 'CC BY 4.0' -or $evidence.permission_to_redistribute_browser_downloadable_glb -ne 'allowed_with_attribution') { Add-ValidationError 'The asset must retain its CC BY 4.0 declaration.' }
    if ($evidence.permission_to_modify -ne $true) { Add-ValidationError 'Adaptation permission must remain recorded.' }

    if ($slot.fallback.kind -ne 'static_svg' -or $slot.fallback.path -ne 'frontend/public/models/ame-terrarium-poster.svg' -or $slot.fallback.runtime_uri -ne '/models/ame-terrarium-poster.svg') { Add-ValidationError 'Unexpected static fallback.' }
    $fallback = [System.IO.Path]::GetFullPath((Join-Path $repoRoot ([string]$slot.fallback.path).Replace('/', '\')))
    if (-not $fallback.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $fallback -PathType Leaf)) { Add-ValidationError 'The static SVG fallback is missing or unsafe.' }
}

$modelsDir = Join-Path $repoRoot 'frontend\public\models'
$oldModels = @('ame.glb','gura.glb','ina.glb','kiara.glb','calli.glb')
foreach ($oldModel in $oldModels) {
    if (Test-Path -LiteralPath (Join-Path $modelsDir $oldModel)) { Add-ValidationError "Removed avatar still exists in the browser build: $oldModel" }
}
if (-not (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $ManifestPath) 'manifest.schema.json') -PathType Leaf)) { Add-ValidationError 'Manifest schema is missing.' }

if ($errors.Count -gt 0) {
    Write-Host "Asset validation failed with $($errors.Count) error(s):" -ForegroundColor Red
    foreach ($validationError in $errors) { Write-Host "  - $validationError" -ForegroundColor Red }
    exit 1
}

Write-Host 'Asset validation passed: one byte-verified CC BY 4.0 Ame terrarium GLB with static fallback.' -ForegroundColor Green
