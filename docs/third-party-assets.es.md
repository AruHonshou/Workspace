# Registro de assets de terceros

[English](third-party-assets.md)

La build local contiene un solo GLB aportado por el usuario: **Smol Ame in an
Upcycled Terrarium** de Seafoam. El código de la aplicación usa Apache-2.0; el
modelo conserva su licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
También se aplican las directrices de fan works de COVER y la identificación
clara del proyecto como no oficial.

| Uso visual | Archivo | Animación | Licencia |
| --- | --- | --- | --- |
| Ame como orquestadora visible dentro del terrario | `ame-terrarium.glb` | `Animation`, 9 segundos en bucle | CC BY 4.0, Seafoam |

El archivo se copió sin modificar a `frontend/public/models`. El manifiesto
registra 4.021.460 bytes, SHA-256
`e794eea8b5e788e394692e8a87e5ca101b220714e51547cc75eb6d37d579a42e`,
fuente, atribución y evidencia de licencia. Los cinco avatares anteriores no se
incluyen ni se descargan en la build.

La escena reproduce el clip original completo y permite rotación, zoom,
desplazamiento limitado y restauración de cámara. No crea subclips. Con
movimiento reducido mantiene una pose estable. Si WebGL o el GLB fallan,
`ame-terrarium-poster.svg` conserva el fondo y todos los controles de la interfaz.

```powershell
./scripts/validate-assets.ps1
```

Consulta [Licencias 3D](licensing.es.md) antes de publicar o cambiar el alcance.
