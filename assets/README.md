# Asset boundary / Límite de assets

The public repository contains one redistributable browser GLB, its license and
provenance metadata, plus a code-authored static fallback. No private authoring
source, voice, song, or undocumented model is included.

El repositorio público contiene un GLB redistribuible para el navegador, sus
metadatos de licencia y procedencia, y un fallback estático creado con código.
No incluye fuentes privadas de edición, voces, canciones ni modelos sin
documentar.

- `manifest.json` is the machine-readable publication gate.
- `manifest.schema.json` documents its stable shape.
- `../frontend/public/models/ame-terrarium-poster.svg` is the code-authored
  fallback shown when WebGL is unavailable.
- `source/`, `private/`, and `models/holomyth/` are intentionally excluded from
  public version control.
- `../frontend/public/models/ame-terrarium.glb` is the byte-verified CC BY 4.0
  runtime asset documented by the manifest.

Run `./scripts/validate-assets.ps1` before every commit. See
[`docs/licensing.md`](../docs/licensing.md) or
[`docs/licensing.es.md`](../docs/licensing.es.md).
