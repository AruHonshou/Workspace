# Solución de problemas de Workspace

[English](troubleshooting.md)

## La búsqueda no inicia

Elige puesto, país, antigüedad y al menos una fuente. Buscar no requiere CV ni DeepSeek. Configura TheirStack para consultar sus portales; Brete/ANE es una fuente independiente para Costa Rica.

Un error del proveedor puede indicar clave rechazada, falta de saldo, límite temporal o indisponibilidad. Revisa Configuración antes de reintentar. Actualizar una página de pago puede consumir créditos.

## No aparecen vacantes

Prueba un puesto más amplio u otra antigüedad: 24 horas, 7 días o 30 días. Revisa los portales seleccionados y las advertencias de cada fuente. La cobertura depende del país y del proveedor.

## Falta un portal

El selector refleja las fuentes compatibles. Los resultados reales dependen de la cobertura de TheirStack o del conector público correspondiente. Workspace no inicia sesión en portales restringidos ni utiliza tus sesiones del navegador.

## Falla una generación de IA

Comprueba la clave de DeepSeek, acceso al modelo y saldo. Selecciona el perfil profesional correcto, confirma el CV requerido y revisa el consentimiento mostrado. Un error de red o del proveedor no significa que se haya borrado tu CV local.

## No se puede importar el PDF

Prueba un PDF sin contraseña y con texto seleccionable. Los documentos escaneados requieren la vía opcional de OCR y sus dependencias del sistema; es preferible un PDF con texto. Revisa el error antes de volver a subir un archivo corrupto.

## Falla el almacén de credenciales

La ejecución local utiliza el almacén seguro del sistema operativo. Los contenedores sin escritorio pueden recibir DEEPSEEK_API_KEY / THEIRSTACK_API_KEY o archivos montados mediante las variables _FILE correspondientes. Las claves inyectadas son de solo lectura en la interfaz.

## No abre el servidor o falla WebGL

Mantén abierta la terminal de desarrollo. Si un puerto está ocupado, detén la instancia anterior antes de iniciar otra. La interfaz abre en http://127.0.0.1:5173/ y el estado del backend se consulta en http://127.0.0.1:8765/health.

Si WebGL no está disponible, la imagen del escritorio de respaldo conserva el acceso y la navegación.

Ejecuta ./scripts/diagnose.ps1 para diagnóstico de solo lectura y ./scripts/test.ps1 para pruebas sintéticas. Elimina claves y datos personales de cualquier log que compartas al informar de un error.
