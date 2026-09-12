# Fuentes y reglas de proveedores

[English](sources-and-tos.md) · Revisado 2026-09-07

TheirStack se consulta mediante su API oficial y una clave del usuario. Puede
devolver anuncios cuya fuente sea LinkedIn, Indeed, Computrabajo, Glassdoor, un
ATS o la empresa. AmeWork conserva la fuente separada del proveedor de datos y
abre la mejor URL original o canónica disponible.
Cuando el usuario selecciona portales compatibles concretos, AmeWork envía el
filtro documentado de dominios URL a TheirStack antes de recibir filas cobrables.
Una búsqueda exclusiva en Brete no llama a TheirStack.

En Costa Rica, el adaptador independiente de Brete/ANE lee únicamente resultados
públicos de empleo. Los proveedores comparten un contrato normalizado, fallan de
forma independiente y usan caché. Una página cobrable nunca se reintenta ni se
carga automáticamente.

AmeWork no scrapea portales restringidos, no usa sesiones/cookies, no evita
CAPTCHA, no rellena formularios y no postula. Las respuestas externas son datos,
no instrucciones. Cada adaptador debe aplicar timeout, tamaño limitado, HTTPS,
atribución, fixtures deterministas y logs sin secretos. Antes de habilitar un
proveedor nuevo se revisan sus términos y su API.
