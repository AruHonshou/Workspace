# Arquitectura

[English](architecture.md)

AmeWork usa FastAPI, SQLite, LangGraph y una interfaz React/Three.js.
El navegador habla únicamente con FastAPI en localhost mediante REST y SSE.

El `StateGraph` coordina cinco roles internos: coordinación, búsqueda, análisis
de encaje, preparación y revisión. Los agentes se crean con LangChain y
`deepseek-v4-pro`; filtros, deduplicación, ranking, límites temporales, selección
de evidencia y PDF continúan siendo deterministas.

TheirStack es el conector principal para Costa Rica. Recupera 25 vacantes por
tanda, cachea cada página y conserva proveedor, portal de origen, enlace de
origen, enlace final y tipo de enlace. Greenhouse, Lever, Ashby, Himalayas, We
Work Remotely, Jobicy, Remotive y Remote OK actúan como respaldo. Los portales
sin integración autorizada también pueden abrirse para importación manual.

Las claves independientes de DeepSeek y TheirStack viven en el Administrador de
credenciales de Windows. El
backend envía únicamente hechos profesionales confirmados sin datos de contacto,
la descripción necesaria de la vacante y contratos JSON tipados. Prompts,
razonamiento y secretos nunca aparecen en SSE.

React muestra una sola escena: el terrario animado de Ame como orquestadora
visible. Los cinco roles del grafo no se convierten en avatares ni conversaciones.
La escena permite rotar, acercar y desplazar de forma limitada, y usa un SVG
estático cuando WebGL o el movimiento no están disponibles.
