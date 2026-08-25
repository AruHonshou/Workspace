# Evaluación

[English](evaluation.md)

La aceptación exige pruebas unitarias de conectores, fechas de 24 h/7 d/30 d,
deduplicación, ranking, credenciales, eventos, subclips y PDF; integración con un
servidor DeepSeek falso; y un E2E desde CV hasta guía de entrevista.

CI no utiliza una clave real. El smoke test real es optativo y se ejecuta sólo
después de introducir la credencial desde la interfaz. Las pruebas comprueban que
la clave, datos de contacto, prompts y razonamiento no aparecen en base de datos,
logs, SSE, checkpoints ni documentos.

Las pruebas de red usan fixtures para paginación, compresión, límites, `429`,
timeouts y fuentes parciales. Ninguna prueba automatiza LinkedIn, Indeed,
Glassdoor o Computrabajo.
