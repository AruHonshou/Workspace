# Workspace visual assets

The landing is an original procedural desk scene. Geometry and materials are authored in frontend/src/components; the browser does not download a third-party character model or soundtrack.

## Shipped resources

- manifest.json: scene and supporting artwork metadata.
- manifest.schema.json: the manifest structure.
- frontend/public/branding/workspace-mark.svg: application mark and favicon.
- frontend/public/branding/desk-fallback.svg: fallback when WebGL is unavailable.
- frontend/public/branding/theme-init.js: initial presentation settings.
- frontend/public/fonts: locally served Inter, Manrope and Caveat fonts with their OFL notices.

Run ./scripts/validate-assets.ps1 to check the scene and static artwork. Font and offline resource checks also run in frontend tests.

The inventory and licensing notices are maintained in [THIRD_PARTY_ASSETS.md](../THIRD_PARTY_ASSETS.md). Keep that document and the manifest aligned with files actually shipped.
