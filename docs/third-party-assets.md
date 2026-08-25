# Third-party asset ledger

[Español](third-party-assets.es.md)

The local build contains one user-supplied GLB: **Smol Ame in an Upcycled
Terrarium** by Seafoam. Application code is Apache-2.0; the model retains its
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) license. COVER fan-work
guidelines and clear unofficial-project identification also apply.

| Visual use | Runtime file | Animation | License |
| --- | --- | --- | --- |
| Ame as the visible orchestrator inside the terrarium | `ame-terrarium.glb` | `Animation`, 9-second loop | CC BY 4.0, Seafoam |

The file was copied unmodified to `frontend/public/models`. The manifest records
4,021,460 bytes, SHA-256
`e794eea8b5e788e394692e8a87e5ca101b220714e51547cc75eb6d37d579a42e`,
source URL, attribution, and license evidence. The previous five avatars are not
included or downloaded by the build.

The scene loops the complete original clip and supports rotation, zoom,
constrained pan, and camera reset. It creates no subclips. Reduced motion keeps a
stable pose. If WebGL or the GLB fails, `ame-terrarium-poster.svg` preserves the
background while all interface controls remain available.

```powershell
./scripts/validate-assets.ps1
```

See [3D asset licensing](licensing.md) before publishing or changing the use
scope.
