# Solución de problemas

[English](troubleshooting.md)

## La búsqueda no inicia

Confirma al menos un CV y elige país y rol válidos. DeepSeek no es necesario para buscar. Si no hay proveedor de pago configurado, las fuentes de respaldo pueden devolver menos resultados. Comprueba cobertura antes de gastar créditos.

Los códigos se muestran sin filtrar secretos: `401/403` es clave rechazada, `402` plan/créditos insuficientes y `429` cuota temporal. Una página cobrable no se reintenta sola; vuelve a solicitarla sólo después de resolver la causa.

## No aparecen vacantes

Prueba un rol amplio, quita la ciudad o habilita remoto mundial. Los resultados nuevos exigen hora exacta dentro de siete días y enlace HTTPS válido. La cobertura varía por país/proveedor y la interfaz nunca afirma cubrir todo Internet.

## Falta un portal

LinkedIn, Indeed, Glassdoor, Computrabajo, Naukri y similares sólo aparecen mediante proveedor autorizado, API/feed oficial o enlace aportado por el usuario. AmeWork no los scrapea directamente ni usa sesiones iniciadas.

## Una función de IA no está disponible

La búsqueda y los resúmenes deterministas siguen funcionando. Para análisis profundo, CV ATS, guía o LinkedIn, valida DeepSeek, concede el consentimiento mostrado y confirma un CV en el idioma de la oferta.

## Falla el almacén de credenciales

Windows usa Credential Manager, macOS Keychain y Linux Secret Service/libsecret. En contenedores sin escritorio, inyecta `*_API_KEY` o monta un archivo y configura `*_API_KEY_FILE`; los secretos inyectados son de sólo lectura en la UI.

## Falla WebGL

La aplicación cambia automáticamente a su imagen estática. Todos los formularios siguen funcionando sin WebGL ni animación.

Ejecuta `./scripts/diagnose.ps1`, `./scripts/test.ps1` y `./scripts/scan-secrets.ps1` para diagnóstico local.
