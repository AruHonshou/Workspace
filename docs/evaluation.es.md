# Evaluación

[English](evaluation.md)

La aceptación exige pruebas unitarias de perfiles múltiples, selección del CV
por idioma, filtro seguro, conectores, fechas de 24 h/7 d/30 d, deduplicación,
ranking, credenciales, eventos, audio y PDF; integración con un servidor
DeepSeek falso; y un E2E desde CV hasta guía de entrevista versionada.

Los PDF sintéticos en español e inglés se extraen a texto y se renderizan página
por página. Deben tener entre 8 y 20 páginas, capa de texto, enlace clicable,
fuentes Unicode, ninguna página vacía y cero referencias a hechos no confirmados.

CI no utiliza una clave real. El smoke test real es optativo y se ejecuta sólo
después de introducir la credencial desde la interfaz. Las pruebas comprueban que
la clave, datos de contacto, prompts y razonamiento no aparecen en base de datos,
logs, respuestas de API ni documentos.

Las pruebas de red usan fixtures para paginación, compresión, límites, `429`,
timeouts y fuentes parciales. Ninguna prueba automatiza LinkedIn, Indeed,
Glassdoor o Computrabajo.
