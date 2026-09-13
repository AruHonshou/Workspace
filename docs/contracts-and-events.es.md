# Contratos públicos

El OpenAPI de ejecución y los modelos Pydantic son la autoridad. El contrato del
navegador se genera con `scripts/generate-contracts.ps1`.

La superficie pública de Workspace contiene salud/sesión, países y proveedores,
configuración de DeepSeek y TheirStack, perfiles y hechos confirmados, búsquedas
sin perfil, vacantes guardadas, herramientas del favorito, importación de
LinkedIn, descargas y exportación/eliminación de datos locales.

Invariantes:

- La búsqueda recibe puesto, país, periodo, portales y página.
- TheirStack es proveedor de datos; LinkedIn, Indeed, Computrabajo y Glassdoor
  son fuentes de la vacante.
- Una operación de IA sobre una vacante guardada exige `profile_id` explícito.
- Las afirmaciones personales citan hechos confirmados; evidencia vacía o
  desconocida no puede convertirse en experiencia dentro del CV ATS.
- Credenciales y contactos nunca aparecen en respuestas, logs o archivos.
- Una base migrada puede conservar campos históricos, pero sus rutas no son
  públicas.

El `X-Session-Token` opcional se envía como header, nunca dentro de una URL.
