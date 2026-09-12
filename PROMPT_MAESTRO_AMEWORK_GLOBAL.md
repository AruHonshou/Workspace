# Prompt maestro de ejecución — AmeWork Global

Trabaja como arquitecto principal, desarrollador full-stack, especialista en LangGraph, seguridad, documentos ATS y QA del proyecto **AmeWork**. Tu misión es transformar el repositorio existente en **AmeWork Global**, una aplicación open source, local, autoalojada y multiplataforma para buscar trabajo en cualquier país, analizar el encaje profesional, guardar favoritos, crear CV compatibles con ATS, preparar entrevistas, optimizar un perfil de LinkedIn y llevar un seguimiento manual de postulaciones.

No entregues únicamente un plan. **Inspecciona, implementa, migra, prueba y verifica la aplicación completa de extremo a extremo.** Avanza de forma autónoma por las fases descritas y no te detengas mientras exista una acción segura y útil dentro del alcance. Si una prueba real requiere una clave privada o un servicio externo no disponible, termina todo con fixtures y servidores simulados, deja ese smoke test como opcional y continúa con el resto.

## 1. Contexto del repositorio

- Trabaja en el repositorio abierto; actualmente está en `C:\Users\arumi\Documents\Codex\2026-08-17\ten`.
- Stack actual:
  - Python 3.12, FastAPI, Pydantic, SQLite y migraciones explícitas.
  - LangChain `create_agent`, LangGraph y checkpoints SQLite.
  - React 19, TypeScript, Vite, Three.js y React Three Fiber.
  - `uv` para Python y `pnpm` para frontend.
  - TheirStack para empleos y DeepSeek para razonamiento estructurado.
- El árbol de trabajo puede contener cambios del usuario. Revísalos y consérvalos. No uses `git reset --hard`, `git checkout --`, borrados masivos ni sobrescribas trabajo ajeno.
- Antes de editar:
  1. Lee `README.md`, `backend/pyproject.toml`, `frontend/package.json` y cualquier `AGENTS.md` aplicable.
  2. Inspecciona esquemas, almacenamiento, API, conectores, agentes, workflows, documentos, tipos y componentes actuales.
  3. Ejecuta una línea base de pruebas y registra fallos preexistentes.
  4. Revisa `git status` y trabaja de forma incremental.
- El estado conocido actual todavía contiene varios supuestos personales: TheirStack fija Costa Rica (`CR`) y 30 días, algunas rutas exigen dos CV, `Interest` mezcla responsabilidades, y parte del flujo utilizado por la UI todavía no pasa realmente por LangGraph. Debes corregirlo sin perder datos.

## 2. Resultado de producto obligatorio

AmeWork Global será una aplicación:

- local, autoalojada, de un solo usuario y disponible en Windows, macOS, Linux y Docker;
- con interfaz en español e inglés;
- capaz de buscar por perfil, rol, país, ciudad o región opcional, modalidad y remoto mundial opcional;
- limitada a vacantes abiertas publicadas durante los últimos **7 días**, con filtros locales de 24 horas y 7 días;
- alimentada principalmente por TheirStack, con arquitectura extensible para JobsPipe y conectores oficiales;
- con perfiles ilimitados y variantes de CV por idioma BCP-47;
- con análisis de encaje honesto y centrado en brechas;
- con Favoritos separados del seguimiento de postulaciones;
- capaz de crear bajo demanda CV ATS en DOCX y PDF y guías de entrevista;
- capaz de analizar un PDF o texto de LinkedIn y devolver recomendaciones copiables;
- sin scraping directo de portales restringidos, autopostulación, lectura de correos, Telegram, n8n, automatización de LinkedIn ni SaaS centralizado.

Conserva sin rediseñar la escena 3D de Ame en el terrario, su animación, música, pantalla de entrada, control de sonido, identidad y estética retro actuales. Mejora o amplía sólo la UI necesaria para las nuevas funciones, respetando el mismo sistema visual.

## 3. Reglas no negociables

### Veracidad y privacidad

- Cero experiencia, métricas, estudios, cargos, certificaciones, tecnologías o logros inventados.
- Cada afirmación personal generada debe enlazar internamente con evidencia confirmada del perfil.
- Los identificadores internos como `fact_id`, UUID, claves de evidencia o referencias técnicas nunca deben aparecer en la UI, DOCX o PDF.
- El PDF original del CV y el PDF de LinkedIn permanecen locales.
- Correo, teléfono, dirección, identificadores y datos de contacto permanecen únicamente en un bloque privado local separado de los registros profesionales; nunca entran en prompts, eventos o documentos intermedios del modelo.
- Antes de enviar información profesional a DeepSeek:
  1. extrae texto localmente;
  2. redacta datos personales;
  3. muestra exactamente el contenido profesional que se enviará;
  4. solicita consentimiento explícito;
  5. permite cancelar sin perder el archivo local.
- DeepSeek será el único proveedor de IA. No reintroduzcas proveedores locales retirados, otro LLM ni fallback silencioso.
- La búsqueda de vacantes debe seguir funcionando sin DeepSeek mediante expansión determinista del rol; los análisis y generaciones que sí necesitan IA deben explicar claramente que requieren DeepSeek.

### Fuentes laborales y cumplimiento

- TheirStack será el proveedor principal y cada usuario aportará su propia clave.
- LinkedIn, Indeed, InfoJobs, Naukri, Computrabajo, Glassdoor y otros portales sólo podrán aparecer cuando TheirStack u otro proveedor autorizado los entregue, o cuando exista una API/feed oficial permitido.
- No implementes scraping directo, navegación automatizada, reutilización de sesiones, cookies o credenciales de esos portales.
- No prometas que todos los portales están presentes en todos los países ni que se cubre todo Internet.
- No llames “LinkedIn”, “Glassdoor” u otro portal a la fuente si los metadatos no lo demuestran. Distingue siempre:
  - proveedor de datos;
  - fuente donde fue descubierta la vacante;
  - URL de origen;
  - URL final para postularse;
  - tipo de URL: `official`, `ats` o `portal`.
- Prioriza `official` y luego `ats`; utiliza `portal` sólo cuando no exista una URL mejor.
- El repositorio nunca debe incluir claves, CV reales, vacantes reales persistidas, copias del dataset ni archivos personales.
- La licencia Apache-2.0 cubre el código, no los datos de terceros.
- Incluye un inventario de proveedores con términos, atribución, usos permitidos y fecha de revisión.
- Antes de declarar lista la publicación mundial, deja como gate explícito obtener confirmación escrita de TheirStack para el uso BYOK dentro de una aplicación open source y realizar una revisión legal. No afirmes “100 % legal”.
- Referencias oficiales que debes verificar al implementar, porque pueden cambiar:
  - TheirStack sources: `https://theirstack.com/en/docs/data/job/sources`
  - TheirStack terms: `https://theirstack.com/en/docs/legal/terms-and-conditions`
  - TheirStack API: `https://theirstack.com/en/docs/api-reference`
  - JobsPipe API: `https://docs.jobspipe.dev/reference/search-jobs`
  - InfoJobs API: `https://developer.infojobs.net/`
  - USAJOBS API: `https://developer.usajobs.gov/`

## 4. Arquitectura objetivo

### Siete agentes exactos

Mantén los cinco roles actuales e incorpora únicamente dos agentes nuevos:

1. `career_coordinator`: coordina, enruta y solicita aprobaciones; no suplanta especialistas.
2. `opportunity_scout`: amplía roles y busca vacantes mediante herramientas autorizadas.
3. `fit_analyst`: crea el análisis requisito-evidencia y prioriza brechas.
4. `application_tailor`: redacta la guía de entrevista usando hechos confirmados.
5. `quality_reviewer`: audita veracidad, cobertura, idioma y calidad; permite una sola corrección.
6. `ats_resume_specialist`: crea propuestas de CV compatibles con ATS.
7. `linkedin_profile_optimizer`: optimiza secciones copiables de LinkedIn.

No crees agentes para PDF, favoritos, deduplicación, filtros, tracking, migraciones o seguridad: esas funciones deben ser deterministas. La extracción estructurada del perfil puede usar DeepSeek como servicio tipado, pero no debe convertirse en un octavo agente.

### Cinco workflows LangGraph reales

Implementa y conecta a las rutas utilizadas por la interfaz:

1. `SearchGraph`: preparación, búsqueda, normalización, validación, deduplicación y encaje rápido.
2. `FitAnalysisGraph`: análisis profundo V2 bajo demanda.
3. `InterviewGuideGraph`: borrador, revisión única, validación y renderizado.
4. `ATSResumeGraph`: selección, reformulación, revisión, aprobación y exportación.
5. `LinkedInOptimizationGraph`: importación estructurada, propuesta, revisión y versionado.

Todos deben usar estado Pydantic/TypedDict claro, checkpoints, cancelación, reanudación e idempotencia. El backend debe emitir sólo eventos sanitizados; nunca prompts internos, chain-of-thought, documentos originales, secretos o conversaciones ficticias. La UI debe mostrar estados neutrales, no los nombres de los agentes.

Reutiliza/cacha el runtime y los agentes DeepSeek mientras no cambie la configuración; no reconstruyas el modelo en cada llamada. Verifica en la documentación oficial los identificadores de modelo vigentes y no hardcodees nombres especulativos.

## 5. Contratos canónicos y persistencia

Pydantic será la fuente de verdad. Exporta JSON Schema y deriva tipos TypeScript para evitar contratos divergentes.

### Perfil profesional

Crea registros estructurados con procedencia por campo:

- `EmploymentRecord`
- `ProjectRecord`
- `SkillRecord`
- `AchievementRecord`
- `EducationRecord`
- `CertificationRecord`
- `LanguageRecord`
- `ResumeVariant`
- `PrivateContactBlock`

Cada registro profesional debe conservar al menos: identificador, contenido estructurado, documento, página, fragmento o span, idioma BCP-47, revisión del perfil y estado de confirmación.

Un perfil estará listo con **una sola variante de CV confirmada**. Puede tener variantes ilimitadas. Si una vacante utiliza otro idioma, genera un borrador de variante a partir de registros confirmados, preserva literalmente nombres, fechas, empresas, métricas y tecnologías, muestra original/traducción y exige aprobación antes de crear documentos. Nunca confirmes automáticamente una traducción.

### Búsqueda y vacantes

Define como mínimo:

- `CountrySearchScope`
- `ProviderCoverage`
- `JobSourceEvidence`
- `JobSearchPage`
- `DeepFitAnalysisV2`

Usa estos enums o equivalentes estables:

- `RemoteEligibility`: `eligible_for_country`, `ineligible`, `unknown`, `worldwide`.
- `ApplyUrlType`: `official`, `ats`, `portal`.
- `CompatibilityStatus`: `compatible`, `review_separately`.

Una ejecución debe guardar de forma inmutable: `profile_id`, revisión de perfil, rol, `country_code`, ciudad/región, modalidades, `include_global_remote`, ventana, instante UTC de inicio, proveedores consultados y páginas cargadas. La paginación posterior debe leer este alcance guardado y nunca el estado actual del navegador.

### Favoritos y documentos

Normaliza los contratos a:

- `Favorite`
- `ATSResume`
- `ATSResumeVersion`
- `InterviewGuideVersion`
- `Application`
- `ApplicationStatusEvent`
- `LinkedInProfileSnapshot`
- `LinkedInOptimizationVersion`

`Favorite` y `Application` son entidades distintas. Un favorito no es un estado del pipeline. Usa `ApplicationStatus` con:

- `planned`
- `applied`
- `no_response`
- `positive_response`
- `interview`
- `technical_test`
- `offer`
- `accepted`
- `rejected`
- `withdrawn`

Cada transición crea un evento inmutable con fecha UTC, estado anterior, estado nuevo y nota opcional.

### Migraciones

- Añade migraciones nuevas y transaccionales; no edites la historia de migraciones ya aplicada.
- Migra CV españoles/ingleses actuales a variantes BCP-47 sin perder archivos ni hechos.
- Conserva búsquedas históricas como Costa Rica/30 días; sólo las nuevas usan país/7 días.
- Convierte cada `Interest` existente en `Favorite` y conserva todas sus guías y PDFs.
- Convierte estados legacy en `Application` únicamente cuando perfil y vacante puedan determinarse sin ambigüedad. Si no, conserva el dato como legacy y no inventes asociaciones.
- Retira el generador ATS legacy del flujo nuevo, pero no borres artefactos existentes.
- Añade rollback seguro dentro de la transacción y pruebas sobre copias sintéticas de bases antiguas.

## 6. API requerida

Mantén compatibilidad temporal con rutas existentes y añade, como mínimo:

- `GET /api/countries`
- `GET /api/providers`
- `GET /api/providers/coverage`
- `POST /api/career/searches`
- `POST /api/career/searches/{run_id}/more`
- `GET /api/career/searches/{run_id}`
- `POST /api/favorites`
- `GET /api/favorites`
- `DELETE /api/favorites/{favorite_id}`
- `POST /api/favorites/{favorite_id}/analyses`
- `POST /api/favorites/{favorite_id}/ats-resumes`
- `PATCH /api/ats-resumes/{resume_id}/approve`
- `GET /api/ats-resumes/{resume_id}.pdf`
- `GET /api/ats-resumes/{resume_id}.docx`
- `POST /api/favorites/{favorite_id}/interview-guides`
- `GET /api/applications`
- `POST /api/applications`
- `PATCH /api/applications/{application_id}`
- `GET /api/applications/{application_id}/timeline`
- `POST /api/linkedin/imports`
- `PATCH /api/linkedin/imports/{snapshot_id}/sections`
- `POST /api/linkedin/imports/{snapshot_id}/optimize`

Payload mínimo de una nueva búsqueda:

```json
{
  "profile_id": "...",
  "role": "Software QA",
  "country_code": "CO",
  "city_or_region": "Bogotá",
  "modalities": ["remote", "hybrid", "onsite"],
  "include_global_remote": false
}
```

Valida el país contra ISO 3166-1 alpha-2. La ventana no será controlable desde el navegador: el backend fija siete días.

Todas las operaciones cobrables o generativas deben aceptar una clave de idempotencia o aplicar una restricción equivalente en almacenamiento. Un doble clic nunca debe consumir páginas, crear favoritos, generar versiones o llamar dos veces al modelo.

## 7. Ejecución por fases

Completa cada fase con backend, frontend, migración y pruebas correspondientes antes de avanzar. No dejes stubs, botones falsos, respuestas hardcodeadas ni TODO como sustituto de funcionalidad.

### Fase 0 — Línea base y protección

1. Audita el estado real del repo y cambios sin confirmar.
2. Ejecuta pruebas backend, frontend, typecheck, lint y build.
3. Identifica dependencias y rutas legacy realmente utilizadas.
4. Crea una estrategia incremental que conserve compatibilidad durante la migración.
5. No modifiques ni regeneres manuales PDF existentes; no se solicita un nuevo manual PDF.

### Fase 1 — Perfil estructurado y consentimiento

1. Implementa registros profesionales y variantes BCP-47.
2. Separa contactos privados de hechos profesionales.
3. Extrae localmente el PDF completo, sin el límite legacy de 40 líneas, con procedencia por página/spans y OCR local si ya existe o está configurado.
4. Añade vista previa redactada, consentimiento y revisión humana por sección.
5. Permite que una sola variante confirmada habilite el perfil.
6. Implementa traducciones provisionales trazables y aprobables.
7. Migra perfiles actuales sin pérdida.

### Fase 2 — Proveedores y búsqueda mundial

1. Crea una interfaz `JobSearchProvider` neutral con capacidades de cobertura y paginación.
2. Refactoriza TheirStack para recibir país y fijar `posted_at_max_age_days: 7`; elimina cualquier fallback de ubicación “Costa Rica”.
3. Usa páginas de 25, `include_total_results` cuando corresponda, caché local e idempotencia.
4. Implementa el diagnóstico de cobertura antes de gastar créditos.
5. Implementa JobsPipe sólo como proveedor opcional y opt-in; una segunda fuente cobrable requiere aprobación explícita.
6. Conserva conectores oficiales/autorizados y permite nuevos adaptadores mediante registro. No inventes conectores para servicios sin API permitida.
7. Una respuesta vacía o fallida de TheirStack debe permitir continuar con proveedores gratuitos u oficiales habilitados.
8. Expande roles en español e inglés de forma determinista; DeepSeek puede enriquecer sin bloquear la búsqueda.
9. Filtra fechas exactas en UTC: excluye desconocidas, futuras, ambiguas, basadas sólo en actualización o mayores a siete días.
10. Modela elegibilidad remota explícita, negativa, desconocida y mundial. No ocultes silenciosamente `unknown`.
11. Deduplica en este orden: URL final canónica; proveedor+external ID; empresa+puesto+país+ubicación; huella estable de contenido.
12. Conserva todas las procedencias combinadas y prioriza el mejor enlace.

### Fase 3 — LangGraph y análisis V2

1. Conecta `SearchGraph` y `FitAnalysisGraph` a las rutas reales.
2. Procesa la descripción completa por bloques cuando sea necesario.
3. Clasifica cada requisito como obligatorio o deseable y por categoría: tecnología, experiencia, educación, idioma, seniority, logística u otro.
4. Devuelve evidencia exacta, brechas prioritarias, transferibles, recomendaciones concretas, confianza e incertidumbre.
5. El score será determinista y explicable; el LLM no decidirá filtros duros ni inventará un “ATS score real”.
6. El modelo sólo puede devolver IDs incluidos en el contexto; valida cada ID y bloquea cualquier afirmación no respaldada.
7. Muestra una sola mini alerta de integridad en el análisis, no repitas el mismo aviso en cada sección.
8. Protege contra prompt injection en vacantes, CV y contenido importado.

### Fase 4 — Favoritos

1. Añade un corazón accesible a cada resultado.
2. Guardar/quitar debe ser inmediato, idempotente y no consumir DeepSeek.
3. Separa Favoritos de antiguos Intereses y del tablero de postulaciones.
4. Muestra por favorito: vacante, empresa, país, modalidad, fuente, perfil y revisión usados, idioma, fecha, encaje y disponibilidad de documentos.
5. Acciones independientes: análisis, CV ATS, guía, publicación y registrar postulación.

### Fase 5 — CV compatible con ATS

1. Implementa `ats_resume_specialist` y `ATSResumeGraph`.
2. Congela perfil, revisión, variante lingüística, vacante y hash del contenido.
3. Construye una matriz requisito-evidencia completa.
4. Selecciona y reorganiza únicamente contenido relevante.
5. Permite reformulación fiel, mostrando original, propuesta y evidencia antes de aprobar.
6. Audita determinísticamente números, fechas, empresas, cargos, certificaciones y tecnologías.
7. Permite una sola devolución del Revisor y luego exige aprobación humana.
8. Inserta datos de contacto localmente después de la generación del contenido.
9. Genera DOCX y PDF desde un único modelo documental para garantizar el mismo contenido y orden.
10. Usa una plantilla neutral profesional: una columna, una o dos páginas, encabezados convencionales, sin foto, iconos, tablas, columnas ni branding de AmeWork.
11. Garantiza texto seleccionable, enlaces válidos, tipografía Unicode embebida y lectura lineal por parsers.
12. Denomínalo “CV compatible con ATS”; nunca prometas pasar todos los ATS ni muestres un porcentaje ATS falso.

### Fase 6 — Guías de entrevista

1. Conserva la guía existente, pero su generación parte ahora de un favorito y se ejecuta bajo demanda.
2. Conecta `InterviewGuideGraph` real con redacción, revisión única y validadores deterministas.
3. Mantén contenido técnico útil, preguntas con respuestas de referencia, relación honesta con experiencia, brechas y preguntas para la empresa.
4. **No incluyas una sección de historias STAR.**
5. No expongas `fact_id`, UUID u otros identificadores internos.
6. Limpia fragmentos de navegación, encabezados de página, pies, código, Markdown crudo y ruido extraído del CV.
7. Versiona la guía y conserva versiones anteriores sin sobrescribirlas silenciosamente.

### Fase 7 — Seguimiento manual

1. Implementa `Application` y eventos de estado inmutables.
2. Añade tablero Kanban y cronología por candidatura.
3. Permite crear una candidatura desde Favoritos y registrar notas/fechas manualmente.
4. No leas correos, cuentas ni mensajes y no cambies estados automáticamente.
5. Depreca el `pipeline_status` global de `JobRecord` sin perder los valores históricos.

### Fase 8 — Optimizador de LinkedIn

1. Implementa `linkedin_profile_optimizer` y `LinkedInOptimizationGraph`.
2. Permite importar el PDF exportado por LinkedIn o pegar secciones manualmente.
3. Extrae y permite corregir: titular, About/resumen, experiencia, educación, habilidades y certificaciones.
4. Usa el perfil seleccionado, roles objetivo, idioma y únicamente evidencia confirmada.
5. El panel mostrará contenido actual, propuesta, motivo, keywords, evidencia presentada de forma humana, contador y botón Copiar.
6. Versiona propuestas y permite comparar cambios.
7. No generes un PDF de LinkedIn, no inicies sesión, no hagas scraping y no modifiques el perfil automáticamente.

### Fase 9 — UI/UX global

1. Conserva la escena 3D y sonido exactamente como funcionan.
2. Añade navegación clara para Mi CV, Buscar, Resultados, Favoritos, Postulaciones y LinkedIn; en móvil usa navegación primaria más un menú “Más”.
3. Implementa selector buscable de países con código ISO como valor canónico y nombre localizado mediante `Intl.DisplayNames` o equivalente con fallback.
4. Muestra filtros de 24 h/7 días, modalidad, fuente, encaje, compatibilidad y elegibilidad remota sin repetir búsquedas.
5. Indica conteo, páginas cargadas, créditos potenciales y cobertura por proveedor antes de “Cargar 25 más”.
6. Renderiza descripciones de forma segura: convierte Markdown/HTML permitido a estructura React saneada; no uses `dangerouslySetInnerHTML`; elimina asteriscos `**` visibles y etiquetas residuales.
7. Mantén selectores personalizados, estados animados, foco visible, teclado, contraste, móvil y `prefers-reduced-motion`.
8. Evita solapamientos de paneles y dropdowns. Prueba alturas pequeñas, zoom del navegador y viewport móvil.
9. No muestres nombres de agentes, chain-of-thought ni conversaciones ficticias.
10. Todas las cadenas nuevas deben existir en español e inglés.

### Fase 10 — Seguridad, multiplataforma y open source

1. Generaliza secretos a Windows Credential Manager, macOS Keychain y Secret Service en Linux mediante `keyring` u otra abstracción segura.
2. En Docker acepta secretos montados o variables inyectadas en runtime, nunca persistidas en SQLite, frontend o imágenes.
3. Mantén backend en loopback por defecto, CORS estricto, token de sesión local y logs redactados.
4. Añade exportación y borrado de datos del usuario.
5. Actualiza `.env.example` sin valores reales.
6. Añade CI para Windows, macOS y Linux, Docker Compose, SBOM, secret scanning y release reproducible.
7. Mantén Apache-2.0 para código y atribuciones separadas para assets.
8. Actualiza README y documentación Markdown en español e inglés: instalación, arquitectura, proveedores, privacidad, agentes, claves, limitaciones, pruebas y contribución.
9. No crees ni actualices un manual PDF.
10. Incluye replay sintético que funcione sin claves, red ni datos personales.

## 8. Pruebas obligatorias

### Backend

- Países ISO válidos e inválidos.
- Fronteras exactas de siete días y 24 horas con zonas horarias.
- Fechas desconocidas, futuras, ambiguas y de actualización.
- TheirStack por país, páginas de 25, conteo, 401/402/429, timeout y respuesta vacía.
- Scope inmutable al cargar más resultados.
- Fallback cuando TheirStack falla o devuelve cero.
- JobsPipe opt-in y prohibición de segundo gasto sin aprobación.
- Deduplicación por URL, IDs y huella entre múltiples proveedores.
- Elegibilidad remota: país, negativa, desconocida y mundial.
- Ausencia total de conectores de scraping directo para portales restringidos.
- Migraciones desde cada versión histórica relevante y conservación de artifacts.
- Perfil con una variante, múltiples variantes y traducción pendiente.
- Redacción de datos personales y consentimiento.
- `DeepFitAnalysisV2` sobre descripciones largas y outputs JSON inválidos.
- Prompt injection y IDs de evidencia no ofrecidos.
- Falsedad personal sembrada y bloqueo por Revisor.
- Favoritos y generaciones idempotentes/concurrentes.
- Aplicaciones y transiciones válidas/inválidas.
- LinkedIn por PDF y texto manual.
- DOCX/PDF con el mismo contenido, capa de texto, Unicode, enlaces y orden de lectura.
- Cero `fact_id` visible y ausencia de sección STAR en guías nuevas.
- Claves ausentes de SQLite; contactos y documentos originales ausentes de prompts, logs, SSE, checkpoints y errores, y accesibles sólo desde su almacenamiento privado local designado.

### Frontend

- Selector global, ciudad, modalidades y remoto mundial.
- Restauración del país y scope al recargar.
- Filtros 24 h/7 días sin llamadas nuevas.
- Corazón accesible e idempotente.
- Favoritos, documentos y tablero de postulaciones.
- Importación y panel copiable de LinkedIn.
- Descripciones Markdown/HTML saneadas.
- Español/inglés, teclado, foco, móvil y reduced motion.
- Escena 3D, música y control de sonido sin regresiones.

### Integración y E2E

Ejecuta al menos este recorrido con datos sintéticos:

1. Crear perfil con un CV confirmado.
2. Elegir Colombia y buscar `QA`.
3. Obtener sólo vacantes de siete días o menos.
4. Filtrar a 24 horas.
5. Cargar otra página sin duplicar crédito ni resultados.
6. Abrir análisis V2.
7. Guardar favorito con el corazón.
8. Crear y aprobar CV ATS DOCX/PDF.
9. Crear guía de entrevista sin STAR ni IDs internos.
10. Registrar la postulación y moverla por el tablero.
11. Importar perfil de LinkedIn y copiar una propuesta.
12. Reiniciar la aplicación y confirmar restauración de todo el estado.

CI debe utilizar fixtures y un servidor DeepSeek/TheirStack simulado. Las pruebas reales con claves son opcionales y nunca deben imprimirlas.

## 9. Comandos de verificación y definición de terminado

Usa los comandos propios del repositorio y, como mínimo:

```powershell
./scripts/test.ps1
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

Además:

- ejecuta lint backend/frontend;
- valida assets;
- ejecuta análisis de secretos;
- busca referencias obsoletas a Costa Rica fija, 30 días y proveedores locales retirados;
- confirma que no existan claves reales, datos personales, `fact_id` visibles ni scraping restringido;
- inicia backend y frontend localmente y realiza un smoke test real de las rutas críticas;
- revisa el diff final para detectar archivos generados, binarios o cambios ajenos accidentales.

El trabajo sólo está terminado cuando:

- todas las fases están implementadas realmente;
- las migraciones conservan datos;
- las rutas usadas por la UI ejecutan los nuevos workflows LangGraph;
- no existen stubs, botones sin función ni respuestas simuladas fuera del modo replay/tests;
- pruebas, typecheck, lint y build pasan;
- la aplicación puede utilizarse sin la escena WebGL mediante el fallback existente;
- el replay funciona sin red ni claves;
- la documentación Markdown describe con honestidad cobertura y limitaciones;
- queda documentado el gate legal de TheirStack para el release global.

## 10. Forma de trabajo y entrega

- Comunica avances breves por fases, pero continúa trabajando.
- Usa subagentes para auditorías o tareas paralelas cuando estén disponibles, sin delegar la responsabilidad de integrar y verificar.
- Haz cambios pequeños y coherentes; prueba en proporción al riesgo después de cada fase.
- No pidas decisiones ya fijadas en este prompt.
- Si encuentras una ambigüedad menor, elige la opción más segura, local, reversible y compatible y documenta la decisión.
- Si una API o término externo cambió, consulta únicamente documentación oficial, adapta la implementación y explica la diferencia.
- No publiques, hagas push, crees releases ni uses claves reales sin autorización explícita.

Al finalizar, responde con:

1. resultado funcional logrado;
2. migraciones y compatibilidad preservadas;
3. pruebas ejecutadas y resultado exacto;
4. rutas principales modificadas;
5. cualquier limitación externa real pendiente, especialmente la confirmación legal de TheirStack o smoke tests que requieran claves.

No cierres con un plan futuro genérico: entrega la implementación completa y verificada.
