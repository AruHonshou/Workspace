# Privacidad y amenazas

[English](privacy-threat-model.md)

- La API y la interfaz escuchan sólo en loopback y usan cookie de sesión HTTP-only.
- La API key se guarda exclusivamente en el Administrador de credenciales de Windows.
- El PDF original, datos de contacto y documentos fuente no salen del equipo.
- DeepSeek recibe hechos profesionales confirmados sin contacto y texto mínimo de la oferta.
- Las ofertas son contenido no confiable y no pueden cambiar instrucciones ni activar herramientas.
- Logs, SSE y errores se sanitizan; el tracing remoto permanece desactivado.
- La aplicación nunca inicia sesión en portales, rellena formularios, envía correos ni postula.
