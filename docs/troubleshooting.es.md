# Solución de problemas

[English](troubleshooting.md)

## La búsqueda no inicia

Confirma el CV y configura DeepSeek en **Configuración**. Configura también
TheirStack para la cobertura principal. Un `401/403` indica una clave rechazada;
un `402` suele indicar créditos insuficientes y un `429`, límite temporal.

## No aparecen ofertas

Prueba un rol más amplio. El resultado excluye fechas desconocidas, publicaciones
de más de 30 días, vacantes cerradas y empleos no ubicados en Costa Rica. Revisa
que TheirStack esté configurado y tenga créditos. Si falla, la interfaz usa las
fuentes de respaldo y avisa que la cobertura es limitada.

## Un portal no aparece integrado

LinkedIn, Indeed, Glassdoor y Computrabajo se abren manualmente. Copia la fecha,
URL y descripción mediante **Importar una vacante encontrada**.

## Animación o WebGL falla

Actualiza el controlador gráfico y confirma que `ame-terrarium.glb` y
`ame-terrarium-poster.svg` existen en `frontend/public/models`. La aplicación
muestra automáticamente el fallback estático si WebGL falla. Movimiento reducido
mantiene una pose estable.

Ejecuta `./scripts/diagnose.ps1` y `./scripts/test.ps1` para un diagnóstico local.
