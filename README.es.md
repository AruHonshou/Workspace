# AmeWork 2

> Espacio open source y local para encontrar empleos recientes, guardar los que valen la pena y preparar una candidatura respaldada por evidencia, sin postular automáticamente.

[English](README.md) · [Documentación](docs/README.md) · [Contribuir](CONTRIBUTING.md) · [Seguridad](SECURITY.md)

![Inicio de AmeWork con el terrario animado de Ame](docs/images/amework-home.png)

## El producto

AmeWork tiene cinco páginas claras:

- **Buscar** — escribe puesto, país, antigüedad (hoy, 7 días o 30 días) y portales. No exige CV ni IA.
- **Favoritos** — conserva vacantes, abre la publicación original y, sólo cuando lo solicitas, analiza brechas, prepara entrevistas o crea un CV ATS.
- **Mi CV** — crea perfiles, importa CV por idioma, revisa datos extraídos y confirma el ledger de evidencia.
- **LinkedIn** — importa el PDF exportado por LinkedIn o texto pegado y genera seis secciones listas para copiar usando el perfil confirmado elegido.
- **Configuración** — guarda TheirStack y DeepSeek en el almacén seguro del sistema operativo, exporta los datos locales o elimínalos.

AmeWork nunca inicia sesión en portales, rellena formularios, envía correos ni presenta candidaturas.

## Cómo busca

`JobSearchService` recibe únicamente puesto, país, ventana de publicación, portales y un identificador idempotente. No depende de perfiles ni IA.

- **TheirStack** es el proveedor BYOK opcional para registros originados en LinkedIn, Indeed, Computrabajo, Glassdoor, páginas empresariales y ATS, sujeto a su cobertura real.
- **Brete/ANE** es un adaptador independiente exclusivo de Costa Rica. Lee tarjetas públicas oficiales sin credenciales ni evasión de controles.
- Proveedor de datos y portal de publicación se almacenan por separado.
- Las vacantes duplicadas se combinan conservando enlaces. Se prioriza empresa, ATS y luego portal.
- Las páginas se cargan manualmente, se cachean 30 minutos y nunca se reintentan solas si el consumo cobrable quedó incierto.
- AmeWork muestra fuentes recuperadas y fallos parciales; nunca promete cubrir todo Internet.

Los portales restringidos no se scrapean directamente. Cuando una vacante procede de ellos, TheirStack es el contrato de datos configurado por el usuario.

## Asistencia respaldada por evidencia

Las funciones opcionales de IA realizan una sola solicitud HTTPS directa a DeepSeek y validan la respuesta con Pydantic. No existe un framework de agentes ni un bucle oculto de herramientas.

El ledger determinista `ProfileFact` es la autoridad. Toda afirmación personal generada debe citar registros confirmados; el código bloquea líneas de CV sin evidencia. Las respuestas técnicas de una guía son material educativo, nunca experiencia atribuida al usuario.

El flujo ATS es explícito:

1. Crear una propuesta de una columna en el idioma de la vacante.
2. Validar cada línea contra hechos confirmados.
3. Mostrar el borrador y posibles problemas.
4. Exigir aprobación humana.
5. Renderizar PDF y DOCX con texto seleccionable.

LinkedIn respeta el mismo límite: primero analiza el PDF o texto de forma determinista y después genera opcionalmente titular, Acerca de, experiencia, educación, habilidades y certificaciones con evidencia.

## Privacidad y seguridad

- CV, hechos, empleos, favoritos, análisis y archivos generados permanecen en el equipo.
- Los proveedores de búsqueda reciben criterios, nunca el CV.
- DeepSeek recibe sólo hechos profesionales confirmados y redactados y el texto necesario, después de mostrar vista previa y solicitar consentimiento.
- Los PDF originales y datos de contacto no se envían a DeepSeek.
- Las claves viven en Credential Manager, Keychain o Secret Service, o en secretos de ejecución. Nunca vuelven al navegador, SQLite, eventos o documentos.
- Todo texto externo se trata como dato no confiable.

## Ejecutar localmente

Requisitos: Python 3.12, `uv`, Node.js 22+, `pnpm` 11.19.0 y PowerShell 7. OCR es opcional.

```powershell
git clone https://github.com/AruHonshou/AmeWork.git
cd AmeWork
Copy-Item .env.example .env
./scripts/bootstrap.ps1
./scripts/dev.ps1
```

Abre [http://127.0.0.1:5173](http://127.0.0.1:5173). La API usa `127.0.0.1:8765` por defecto. Docker de desarrollo está disponible con `docker compose up --build`.

## Calidad

```powershell
./scripts/test.ps1
./scripts/generate-contracts.ps1
./scripts/validate-assets.ps1
./scripts/scan-secrets.ps1
./scripts/generate-sbom.ps1
```

Las pruebas usan proveedores falsos y perfiles sintéticos; no gastan créditos reales.

## Licencia

El código usa [Apache-2.0](LICENSE). Los recursos externos conservan licencia y procedencia en [THIRD_PARTY_ASSETS.md](THIRD_PARTY_ASSETS.md) y [`assets/manifest.json`](assets/manifest.json).

**Smol Ame in an Upcycled Terrarium** es obra de **Seafoam** bajo CC BY 4.0. AmeWork es un proyecto fan no oficial, sin afiliación ni respaldo de COVER Corporation ni hololive production.
