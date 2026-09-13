# Validación de Workspace

[English](evaluation.md)

Ejecuta ./scripts/test.ps1 desde la raíz. Valida assets, ejecuta pruebas de backend y frontend, comprueba lint de Python y TypeScript y compila el frontend. La opción -Quick omite el lint de Python y los pasos de lint/build de producción del frontend.

La suite cubre:

- Perfiles, confirmación, selección de idioma y evidencia profesional.
- Proveedores, paginación, fechas, caché y deduplicación.
- Favoritos, candidaturas e información profesional adicional.
- Brechas, entrevistas, CV ATS y propuestas de LinkedIn.
- Migraciones de base de datos y conservación de registros.
- Credenciales, validación de entradas y contratos públicos.
- Rutas, navegación, documentos y migración de preferencias.
- Geometría del escritorio, proyección, interacción y recursos locales.

Utiliza perfiles, PDF y respuestas de proveedores sintéticos. Las pruebas no deben requerir claves reales, consumir créditos ni enviar datos profesionales a terceros.

Los documentos deben tener texto legible, enlaces utilizables y afirmaciones respaldadas por evidencia. No se exige una cantidad de páginas única: un CV y una guía de entrevista tienen propósitos diferentes.

Cuando cambie el renderizado, revisa PDF representativos y pantallas responsive además de las pruebas automáticas. La validación de assets, revisión de secretos y comprobación de contratos generados son verificaciones adicionales del repositorio.
