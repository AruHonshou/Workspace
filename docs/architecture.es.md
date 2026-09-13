# Arquitectura de Workspace

Workspace es una aplicación local construida con React y FastAPI. SQLite almacena
perfiles, evidencias confirmadas, búsquedas, vacantes normalizadas, favoritos y
documentos. El navegador usa REST; la aplicación no inicia sesión en portales ni
envía postulaciones.

## Flujo activo

1. `/buscar` envía puesto, país, antigüedad y portales a `JobSearchService`. No
   exige CV ni clave de IA.
2. `TheirStackProvider` obtiene anuncios de portales y `BreteProvider` aporta la
   fuente pública de empleo de Costa Rica. Cada proveedor puede fallar por separado.
3. Procesos deterministas normalizan, eligen la URL canónica y fusionan duplicados.
   Una caché breve en SQLite evita repetir consultas idénticas y sólo se pide otra
   página cuando el usuario pulsa **Cargar más**.
4. `/favoritos` guarda una vacante. Su página de detalle puede combinarla con un
   perfil para analizar brechas, preparar una entrevista o crear un CV ATS.
5. `DeepSeekProvider` llama directamente a la API oficial y valida la respuesta con
   Pydantic. Los validadores de evidencia bloquean afirmaciones personales sin
   respaldo antes de renderizar documentos.
6. `/linkedin` extrae localmente el PDF aportado, ejecuta comprobaciones objetivas y,
   si el usuario lo pide, genera mejoras vinculadas a evidencia con DeepSeek.

## Límites de privacidad

- TheirStack sólo recibe criterios de búsqueda, nunca el CV.
- DeepSeek recibe únicamente hechos profesionales confirmados necesarios para una
  operación solicitada; contactos y archivos originales permanecen locales.
- Las claves se guardan en el almacén seguro del sistema operativo o como secreto
  de ejecución, nunca en SQLite ni en el navegador.
- La escena 3D es sólo presentación y todo funciona sin WebGL.

El contrato público está en `frontend/src/generated/openapi.json`. Los campos
históricos de la base se conservan exclusivamente para migrar instalaciones sin
perder datos; no forman parte de las rutas públicas de Workspace.
