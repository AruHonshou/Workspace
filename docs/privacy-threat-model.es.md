# Privacidad y amenazas

[English](privacy-threat-model.md)

- La API y la interfaz escuchan sólo en loopback y usan cookie de sesión HTTP-only.
- Las claves usan Credential Manager, Keychain o Secret Service; los contenedores
  pueden recibir secretos runtime de sólo lectura.
- Los PDF originales y contactos privados permanecen locales. Sólo la vista
  profesional redactada que el usuario ve y aprueba puede llegar a DeepSeek.
- Los proveedores laborales reciben rol/geografía y nunca datos del candidato.
- DeepSeek recibe registros confirmados mínimos y texto de la oferta únicamente
  tras consentimiento por finalidad.
- Las ofertas son contenido no confiable y no pueden cambiar instrucciones ni activar herramientas.
- Logs y errores se sanitizan; el tracing remoto permanece desactivado.
- Al borrar un perfil o Favorito también se eliminan sus PDF/DOCX generados
  registrados, pero únicamente cuando la ruta resuelta permanece dentro del
  directorio de artefactos configurado por Workspace.
- La aplicación nunca inicia sesión en portales, rellena formularios, envía correos ni postula.
