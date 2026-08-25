# Fuentes de vacantes y términos de servicio

[English](sources-and-tos.md) · Última revisión: 2026-08-20

AmeWork es un lector personal, no un redistribuidor de contenido.
Conserva procedencia, enlaza la oferta original, consulta con moderación y nunca
envía una candidatura.

## Fuente principal: TheirStack

TheirStack se consulta mediante `POST /v1/jobs/search` con `country_code=CR`,
vacantes abiertas y una antigüedad máxima de 30 días. La aplicación pide 25
registros por tanda, cachea cada página y no reintenta automáticamente una página
cobrable. Cada vacante devuelta puede consumir un crédito. Se conserva por
separado el proveedor TheirStack, el portal de origen, la URL de origen, la URL
final y el tipo de enlace. Consulta su documentación de
[fuentes](https://theirstack.com/en/docs/data/job/sources),
[créditos](https://theirstack.com/en/docs/pricing/credits) y
[paginación](https://theirstack.com/en/docs/api-reference/pagination).

TheirStack puede devolver publicaciones procedentes de LinkedIn, Indeed,
Glassdoor, Computrabajo, ATS y páginas corporativas. Eso no autoriza a esta
aplicación a automatizar esos portales: nunca usa sus sesiones, cookies ni HTML.

## Conectores de respaldo

| Conector | Superficie autorizada | Política local |
| --- | --- | --- |
| Greenhouse | Endpoints `GET` públicos y sin autenticación del [Job Board API](https://developers.greenhouse.io/job-board.html) | El usuario configura el board token; cachear y enlazar el formulario alojado |
| Lever | `GET` públicos del [Postings API oficial](https://github.com/lever/postings-api) | Configurar slug de empresa; nunca usar el `POST` de candidatura |
| Ashby | [Public Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api) | Configurar el nombre del job board y leer sólo puestos publicados |
| Himalayas | [API pública](https://himalayas.app/docs/remote-jobs-api) | Actualización diaria, manejar `429`, conservar atribución y enlace |
| We Work Remotely | [Feeds RSS públicos](https://weworkremotely.com/remote-job-rss-feed) | Consulta conservadora con atribución/backlink |
| Jobicy | [Feed/API pública](https://jobicy.com/jobs-rss-feed) | Máximo 100 registros por respuesta; conservar fecha y atribución |
| Remotive | [API pública](https://github.com/remotive-io/remote-jobs-api) | Backlink, catálogo en caché y frecuencia acorde con su política publicada |
| Remote OK | [API pública](https://remoteok.com/api) | Conservar atribución y URL original; cachear catálogo |
| Manual | URL, hora exacta y texto aportados por el usuario | Sin petición de red; identificar importaciones de portales restringidos |

Que un board ATS tenga `GET` público no concede permiso general para replicar su
base. Consulta sólo boards elegidos por el usuario, conserva los campos mínimos,
respeta caché cuando exista y elimina registros caducados según la política
local.

## Fuentes opcionales pospuestas

- [USAJOBS](https://developer.usajobs.gov/api-reference/get-api-search) es una
  API oficial válida para empleo federal; requiere clave e identificación por
  email/User-Agent.
- [Adzuna](https://developer.adzuna.com/docs/terms_of_service) requiere clave,
  atribución/backlink y respeto de cuota/licencia.

No hacen falta para una v1 útil. Activarlas requiere revisión y fixture
determinista propios.

## Automatización directa prohibida

- El [acuerdo de LinkedIn](https://www.linkedin.com/legal/user-agreement)
  prohíbe scraping, crawlers y automatización no autorizada. Su
  [Job Posting API](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview?view=li-lts-2026-03)
  publica ofertas para partners aprobados; no es una API pública de búsqueda.
- Los [términos de Indeed](https://www.indeed.com/legal?hl=en_US) prohíben
  extracción, agentes y postulaciones automatizadas no autorizadas. Su
  [Job Sync API](https://docs.indeed.com/job-sync-api) es para ATS partners.
- [Glassdoor](https://www.glassdoor.com/about/terms/) restringe extracción
  automática sin permiso.
- [Computrabajo](https://co.computrabajo.com/avisolegal/) permanece sólo como
  enlace de navegador hasta disponer de una integración autorizada.

No uses cookies del navegador, extensiones, APIs no oficiales, scraping de
resultados, CAPTCHA bypass ni la sesión autenticada del usuario. La interfaz
abre una búsqueda equivalente en otra pestaña; el usuario pega URL, fecha y
hora exactas, y texto visible en el importador manual.

## Reglas para URL y correo manuales

Una URL de ATS conocido se resuelve con su endpoint documentado. Para un sitio
desconocido se pide pegar la descripción visible; una URL no se convierte en
crawler. Un futuro fetch opt-in debe exigir HTTPS, DNS a direcciones públicas,
límites de redirects/tamaño/tipo, revisión de robots/ToS y sólo datos visibles
[`JobPosting`](https://schema.org/JobPosting).

En v1 el correo se pega o importa localmente como `.eml`; no se autoriza todo el
buzón. Los scopes de lectura de Gmail son [restringidos](https://developers.google.com/workspace/gmail/api/auth/scopes)
y `Mail.Read` de [Microsoft Graph](https://learn.microsoft.com/en-us/graph/permissions-reference)
también da acceso amplio. Una integración futura necesita otra revisión de
privacidad y mínimo privilegio.

## Checklist de conectores

- ID de fuente, URL canónica, fecha de recuperación y hash.
- Timeouts, tamaño máximo, reintentos con backoff y rate limit por proveedor.
- User-Agent/contacto veraz cuando se exija.
- Nada de secretos o payload crudo en SSE/logs.
- Saneamiento antes del modelo; el texto externo es dato, no instrucción.
- Fixtures deterministas y replay con cero red.
- Atribución visible al mostrar contenido del proveedor.
- Navegación humana al sitio original; nunca `POST` de candidatura.

APIs y términos pueden cambiar. El conector debe fallar cerrado ante cambios y
la fecha de revisión sólo se actualiza tras comprobar estas fuentes primarias.
