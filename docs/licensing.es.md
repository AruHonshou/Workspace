# Licencias 3D y gate de publicación

[English](licensing.md) · Última revisión: 2026-08-29

Es una lista técnica de cumplimiento, no asesoría legal. Mandan los términos
exactos aceptados al obtener cada archivo.

## Dos distribuciones independientes

1. Un FBX/GLB en GitHub público puede copiarse y bifurcarse. GitHub exige que
   quien publica tenga derechos para ello ([Terms §§5–6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service?apiVersion=2022-11-28)).
2. Un visor interactivo envía los bytes GLB al navegador. CDN, Git LFS, base64,
   URL firmada, compresión, conversión u ofuscación no lo convierten en una
   simple imagen renderizada.

Que no haya monetización no corrige una prohibición de redistribución. “Gratis”
y “royalty-free” no autorizan archivos fuente. Apache-2.0 cubre sólo el código y
no relicencia assets de terceros.

## Resultado típico por licencia

| Licencia | Repo público + GLB web | Condiciones |
| --- | --- | --- |
| [CC0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en) | Normalmente sí | Verificar procedencia y derechos de marca/imagen; acreditar sigue siendo buena práctica |
| [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Sí | Crédito, enlace de licencia/fuente, avisos y cambios; sin restricciones adicionales |
| CC BY-SA 4.0 | Sí | Las modificaciones del modelo usan la misma licencia; separar licencia de código/asset |
| CC BY-NC 4.0 | Sólo uso realmente no comercial | Mala base para software público reutilizable; el uso comercial downstream sigue prohibido |
| [CC BY-ND 4.0](https://creativecommons.org/licenses/by-nd/4.0/) | Sólo sin adaptar | No publicar cambios artísticos/rig/animación; revisar con cuidado la conversión técnica |
| Editorial | Normalmente no | Sólo contexto informativo/crítico autorizado, no decoración/promoción |
| Estándar/royalty-free | Normalmente no el archivo | Suele permitir renders o producto incorporado con protección antiextracción |
| Sin licencia/fuente | No | Poder descargar no es permiso de redistribución |

Para CC registra Título, Autor, Fuente, Licencia y modificaciones como recomienda
[Creative Commons](https://creativecommons.org/reusing-cc-licensed-content/).
CC no despeja automáticamente marcas, imagen/privacidad, derechos morales ni
franquicias de terceros.

Ejemplos de términos restrictivos:

- [Sketchfab Standard](https://sketchfab.com/licenses) prohíbe permitir descarga,
  extracción o acceso standalone.
- [CGTrader Royalty Free](https://help.cgtrader.com/hc/en-us/articles/360015124437-Royalty-Free-License)
  exige producto incorporado del cual no pueda recuperarse el modelo.
- [Unity Asset Store](https://assetstore.unity.com/ko-KR/browse/eula-faq) sólo
  admite un asset incorporado en un producto sustancial sin extracción.
- [Fab Standard](https://www.fab.com/eula?lang=en) permite proyectos incorporados,
  no redistribución standalone.
- [TurboSquid](https://www.turbosquid.com/licensing) impone condiciones WebGL
  que un GLB público normal no satisface automáticamente.
- Adobe permite Mixamo en proyectos, pero sus [términos de Content Files](https://www.adobe.com/legal/terms.html)
  prohíben distribución standalone. Las animaciones se revisan por separado.

## Evidencia registrada por modelo

1. Autor/titular y URL original.
2. Licencia exacta, texto/permalink y fecha.
3. Recibo/prueba ligada a persona/entidad y seats correctos.
4. Atribución y avisos.
5. Permiso de modificación.
6. Permiso explícito para GLB descargable, GitHub público y forks.
7. Procedencia/licencia de malla, texturas, materiales, rig y animaciones.
8. Log de conversión/modificación.
9. Revisión de marca, personaje, voz e imagen.
10. Checksum, revisor, fecha y decisión.

Un uploader no puede licenciar un modelo extraído de un juego. Una etiqueta CC
no corrige falta de titularidad. Ante duda, el modelo vuelve al avatar
procedural neutral.

## Procedimiento

El [`assets/manifest.json`](../assets/manifest.json) y su schema actuales admiten
exactamente un GLB: **Smol Ame in an Upcycled Terrarium** de Seafoam, CC BY 4.0,
aportado por el usuario y verificado por bytes. Está marcado
`included_local_noncommercial` y `publishable: true` con atribución obligatoria.
El validador comprueba ruta, tamaño, SHA-256, evidencia, animación y fallback.

El manifiesto también registra `UKLELESONG.mp3` y `ame.png`, archivos aportados
por el propietario con autorización expresa para incluirlos y redistribuirlos
en AmeWork. Conservan checksum, tamaño, nombre original y una licencia separada
del código. El audio es opcional y la aplicación sigue funcionando si falla.

Para reemplazos o assets futuros:

- guarda fuera de Git la evidencia con pagos/cuentas;
- publica un registro redactado y la atribución;
- relaciona cada archivo y checksum con ese registro;
- exclúyelo expresamente de Apache o registra su licencia abierta compatible;
- valida entrega web, no sólo derechos de autoría/render;
- revisa licencia, seguridad, rendimiento y accesibilidad.

Hasta entonces se usa el fallback estático. Nunca reemplaces primero y verifiques
después: forks y cachés dificultan retirar copias.

## Estrategia render-only

Si sólo se permiten uso y renders:

- fuente fuera del repo y placeholder CC0/local;
- imagen, vídeo o sprites renderizados si la licencia los permite;
- embed oficial si plataforma y modelo lo autorizan; o
- sustitución/permiso escrito que cubra WebGL público y GitHub.

Un build privado no resuelve un visor público: el navegador recibe el modelo.
Cifrado o conversión no sustituyen permiso.
