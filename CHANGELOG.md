# Historial de versiones

Todos los cambios relevantes de Workspace se documentan en este archivo.

## 1.0.1 — 2026-09-13

Actualización correctiva de estabilidad y experiencia de uso para el optimizador de LinkedIn.

### Mejoras

- LinkedIn vuelve a solicitar únicamente las secciones que DeepSeek haya omitido o respaldado con identificadores inválidos.
- Si el segundo intento tampoco puede validarse, Workspace conserva de forma segura el contenido importado de esa sección sin descartar el resto del perfil.
- Los errores de importación, análisis estructural y generación se presentan en español o inglés según el idioma de la interfaz.
- La generación muestra un estado de progreso claro y evita ejecuciones duplicadas mientras está activa.
- La barra de acciones de LinkedIn mantiene sus controles alineados y adaptables, sin superposiciones del selector de archivos.

### Validación

- Pruebas específicas para recuperación selectiva y respaldo seguro de secciones de LinkedIn.
- Suite completa de backend y frontend, compilación de producción, validación de estilo, recursos, licencias y secretos.

## 1.0.0 — 2026-09-13

Primer lanzamiento público estable de Workspace.

### Funciones principales

- Escritorio 3D interactivo y navegación interna con apariencia de navegador.
- Búsqueda de vacantes por puesto, país, fecha y fuente mediante TheirStack, con soporte complementario para Brete/ANE en Costa Rica.
- Normalización, deduplicación, caché, paginación y acceso a la publicación original.
- Favoritos y seguimiento manual de candidaturas por etapas.
- Perfiles profesionales independientes con CV en español e inglés.
- Banco local de información profesional en Sobre mí.
- Análisis de brechas basado en evidencia confirmada.
- Guías de entrevista contextualizadas para cada vacante.
- Creación y exportación de CV ATS con revisión humana y controles contra afirmaciones no respaldadas.
- Análisis del PDF exportado de LinkedIn y propuestas listas para copiar y pegar.
- Datos profesionales almacenados localmente y credenciales protegidas por el sistema operativo.
- Interfaz disponible en español e inglés.

### Requisitos

- Git.
- Python 3.12 y `uv`.
- Node.js 22 o superior.
- pnpm 11.19.0.
- Navegador moderno con WebGL.
- Claves propias de TheirStack y DeepSeek para las funciones que utilizan esos servicios.

### Alcance y limitaciones conocidas

- Workspace no postula automáticamente ni inicia sesión en portales de empleo.
- La cobertura y el consumo de créditos de búsqueda dependen de TheirStack y de cada fuente.
- DeepSeek es un servicio externo: requiere una clave válida, conectividad y saldo o cuota disponible.
- Los resultados generados por IA deben ser revisados por la persona antes de utilizarlos.
- El formato ATS mejora la legibilidad automática, pero no garantiza una entrevista o contratación.
- Los PDF escaneados pueden necesitar las dependencias opcionales de OCR.
- La escena 3D requiere más descarga inicial que las páginas internas; existe una presentación de respaldo cuando WebGL no está disponible.

### Validación del lanzamiento

- Pruebas automatizadas de backend y frontend.
- Compilación de producción del frontend.
- Verificación de tipos y estilo.
- Validación de recursos y licencias.
- Escaneo preventivo de secretos.
- Construcción mediante Docker Compose.
- Instalación limpia desde el repositorio.
