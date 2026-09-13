# Workspace

Workspace es una aplicación local para organizar una búsqueda laboral, preparar candidaturas y mejorar la presencia profesional con ayuda opcional de inteligencia artificial.

> Workspace es la evolución actual del proyecto que anteriormente se conocía como AmeWork. Este repositorio documenta la versión moderna, simplificada y orientada a uso personal local.

## Qué es Workspace

Workspace no es un portal de empleo ni un sistema de aplicación automática. Es un espacio de trabajo profesional que reúne:

- Buscadores de empleo.
- Documentos profesionales.
- Análisis de requisitos.
- Preparación para entrevistas.
- Generación de documentos orientados a una vacante.
- Seguimiento del proceso de selección.
- Mejora del perfil de LinkedIn.

La aplicación abre siempre la publicación original de la vacante. No inicia sesión en portales de empleo, no rellena formularios automáticamente y no envía candidaturas en nombre del usuario.

El diseño es local-first: perfiles, documentos, favoritos, análisis y configuraciones se almacenan en la instalación local. Los servicios externos solo reciben los datos estrictamente necesarios para la operación solicitada.

## Principios del producto

### Local-first

Workspace está pensado para ejecutarse en el equipo del usuario. Esto permite conservar el control sobre los CV, datos de contacto, notas, historial y documentos generados.

### IA bajo demanda

La búsqueda y la organización básica no dependen de DeepSeek. La inteligencia artificial se utiliza cuando el usuario solicita una acción concreta:

- Analizar brechas.
- Preparar una entrevista.
- Crear un CV ATS.
- Mejorar un perfil de LinkedIn.

### Evidencia antes que invención

La IA puede mejorar la redacción, ordenar información y adaptar el lenguaje a una vacante, pero no debe inventar experiencia, tecnologías, fechas, métricas, empresas, títulos ni certificaciones.

### Publicación original

Workspace ayuda a investigar y preparar una candidatura, pero la decisión y el envío final siempre permanecen con el usuario.

### Fallos parciales y transparencia

Si una fuente de empleos no responde, las demás pueden seguir entregando resultados. La interfaz debe explicar qué fuentes funcionaron, cuáles fallaron y qué datos se obtuvieron.

## Experiencia y navegación

La interfaz interna utiliza una metáfora de navegador profesional dentro de un workspace 3D. Cada módulo tiene una ruta propia y puede abrirse como una página completa:

| Ruta | Módulo |
| --- | --- |
| / | Inicio y escena 3D interactiva |
| /buscar | Búsqueda de empleos |
| /favoritos | Vacantes guardadas |
| /favoritos/:id | Detalle de una vacante guardada |
| /mi-cv | Perfiles profesionales y documentos |
| /sobre-mi | Banco de información profesional |
| /candidaturas | Seguimiento de procesos |
| /linkedin | Analizador de perfil de LinkedIn |
| /configuracion | Proveedores, IA y datos locales |

La landing muestra un escritorio en primera persona. El monitor es el punto de entrada principal a los módulos. La escena conserva interacciones con el monitor y objetos del escritorio, como el cuaderno, el ratón y la taza.

## Módulos

### Inicio

La página de inicio presenta el workspace 3D y el acceso a la aplicación. El usuario puede observar la escena con un movimiento suave de cámara y entrar al espacio de trabajo desde el monitor.

### Buscar empleos

Permite elegir puesto, país, ventana de publicación, fuentes disponibles, modalidad e inclusión de oportunidades remotas cuando corresponda.

Los resultados se normalizan para presentar una experiencia homogénea aunque provengan de portales distintos. El usuario puede abrir la publicación original o guardarla en Favoritos.

### Favoritos

Centraliza las vacantes que el usuario desea revisar más adelante. Cada favorito conserva la información útil de la oferta y permite abrir el portal, elegir el perfil profesional, analizar brechas, preparar entrevista, crear un CV ATS y marcar el puesto dentro del flujo de candidatura.

### Mi CV

Permite crear varios perfiles profesionales, por ejemplo QA Automation, Software Engineer, Ciberseguridad o Data Analyst. Cada perfil puede conservar documentos en español e inglés.

El proceso de un CV sigue tres etapas:

1. Importar el documento.
2. Revisar los datos extraídos.
3. Confirmar la información que podrá utilizar la IA.

### Configuración

Concentra los ajustes de TheirStack, DeepSeek, idioma, datos locales, diagnóstico de conexión y exportación o eliminación de datos. Las claves de API se configuran localmente y no deben incluirse en el repositorio.

## Flujo principal

~~~text
1. Crear un perfil profesional en Mi CV.
2. Importar el CV en español, inglés o ambos idiomas.
3. Revisar y confirmar la información detectada.
4. Ir a Buscar empleos.
5. Buscar un puesto y seleccionar filtros.
6. Guardar las vacantes de interés.
7. Abrir un favorito.
8. Seleccionar el perfil que se utilizará para documentos.
9. Analizar brechas, preparar entrevista o crear un CV ATS.
10. Abrir la publicación original y gestionar el proceso en Candidaturas.
~~~

La búsqueda puede utilizarse sin configurar IA. Las funciones inteligentes se ejecutan únicamente cuando el usuario las solicita.
## Búsqueda de empleo

### Proveedores y fuentes

Workspace separa dos conceptos:

- Proveedor de datos: el servicio técnico que entrega la información.
- Fuente de la vacante: el portal donde se publicó el empleo.

TheirStack puede funcionar como proveedor unificado para fuentes como LinkedIn, Indeed, Computrabajo, Glassdoor, InfoJobs u otras disponibles en su cobertura. En la interfaz el usuario debe ver la fuente real de la vacante, no confundirla con el proveedor técnico.

Para Costa Rica se contempla también la integración de fuentes locales compatibles, como Brete/ANE, sin mezclar su lógica con TheirStack.

### Normalización

Cada resultado se transforma al modelo común de empleo. La normalización contempla título, empresa, ubicación, modalidad, fecha de publicación, descripción, requisitos, URL canónica, fuente original e identificador externo.

### Duplicados

La misma vacante puede aparecer en varios portales. Workspace puede agrupar resultados con señales como:

- Empresa normalizada.
- Título normalizado.
- Ubicación.
- URL.
- Similitud de descripción.

La oferta agrupada puede conservar varias URLs de origen y mostrar cuál portal la publicó.

### Caché y consumo

Las búsquedas repetidas deben aprovechar la caché local para evitar peticiones innecesarias y reducir el consumo de créditos. La paginación es manual: se muestran resultados iniciales y el usuario solicita más cuando lo necesita.

Si una fuente falla, la búsqueda conserva los resultados de las fuentes que sí respondieron.

## Perfiles y CV

Un perfil profesional representa una versión enfocada de la experiencia del usuario. Puede tener nombre, rol objetivo, CV en español, CV en inglés, información extraída, hechos confirmados, estado de revisión y fecha de actualización.

El idioma de una oferta ayuda a elegir el CV correspondiente:

- Oferta en inglés: se utiliza el CV en inglés.
- Oferta en español: se utiliza el CV en español.

El análisis de brechas se presenta en español por defecto y puede traducirse desde la interfaz cuando el usuario lo solicita.

### Hechos profesionales

Los hechos confirmados funcionan como un registro de evidencia. Pueden representar:

- Tecnologías y herramientas.
- Responsabilidades y logros.
- Fechas y empresas.
- Estudios, certificaciones e idiomas.

Una generación debe poder relacionar sus afirmaciones con hechos existentes. Si no existe evidencia suficiente, el sistema debe expresarlo como brecha o dato pendiente, no convertirlo en una afirmación falsa.

## Favoritos y análisis

En el detalle de un favorito se combinan los datos de la vacante, su descripción, los requisitos detectados, el perfil seleccionado y las acciones de preparación.

### Análisis de brechas

El análisis compara la vacante con el CV del perfil elegido y devuelve:

- Requisitos respaldados por el CV.
- Fortalezas relevantes.
- Requisitos parcialmente respaldados.
- Tecnologías o conocimientos no encontrados.
- Información que requiere confirmación.
- Recomendaciones realistas antes de postular.

El análisis no debe limitarse a copiar el CV ni a mostrar un porcentaje sin explicación. Su objetivo es explicar la distancia entre el puesto y la evidencia disponible.

## Preparación de entrevistas

La guía de entrevista se adapta al idioma de la oferta y puede incluir:

- Resumen del puesto.
- Tecnologías y responsabilidades relevantes.
- Fortalezas del perfil.
- Brechas que conviene preparar.
- Preguntas técnicas y conductuales.
- Temas de estudio.
- Preguntas que el candidato puede hacer.
- Plan de preparación.

La guía se puede consultar en pantalla y generar como PDF cuando la funcionalidad esté disponible.

## Generación de CV ATS

El CV ATS se crea para una vacante concreta a partir de:

1. El CV del perfil seleccionado.
2. La descripción de la vacante.
3. Los requisitos detectados.
4. Los hechos profesionales confirmados.
5. La información adicional de Sobre mí.

La IA adapta la redacción y prioriza palabras clave respaldadas por evidencia. No debe copiar el CV original sin análisis ni rellenar el documento con afirmaciones nuevas.

El documento ATS debe mantener una estructura simple y legible:

~~~text
Nombre y datos de contacto

Resumen profesional

Habilidades

Experiencia

Proyectos

Educación

Certificaciones
~~~

El renderer controla el diseño final del PDF para mantener compatibilidad con sistemas ATS. Se evita depender de columnas, gráficos, iconos, barras de nivel, tablas decorativas o información que dificulte la extracción de texto.
## Sobre mí

Sobre mí es un banco de información profesional complementario al CV. Puede contener:

- Estudios.
- Proyectos.
- Portafolio y sitios web.
- GitHub.
- Certificaciones.
- Experiencia adicional.
- Logros.
- Preferencias profesionales.
- Objetivos de carrera.

La información se guarda localmente y puede actualizarse. Su propósito es aportar contexto verificable para el CV ATS, el análisis de brechas y la mejora de LinkedIn.

## Candidaturas

Candidaturas funciona como un mini CRM personal. Una vacante puede avanzar por estados como:

- Guardada.
- Postulada.
- Contactado.
- Revisión inicial.
- Entrevista.
- Prueba técnica.
- Oferta.
- Contratado.
- Rechazado.
- Cerrado.

Cada registro puede conservar empresa, puesto, ubicación, perfil utilizado, fecha, estado actual, notas e historial de cambios.

El sistema ayuda a organizar el proceso, pero no envía mensajes ni aplica automáticamente.

## Analizador de LinkedIn

El usuario puede exportar su perfil de LinkedIn como PDF y subirlo a Workspace. El flujo utiliza:

- El perfil profesional seleccionado en Mi CV.
- El idioma de salida.
- El objetivo profesional.
- La información de Sobre mí.
- El PDF exportado de LinkedIn.

Primero se extrae la estructura del PDF y después se analiza con IA. Las áreas principales son:

- Titular.
- Acerca de.
- Experiencia.
- Educación.
- Habilidades.
- Certificaciones.

El resultado está pensado para copiar y pegar en LinkedIn. Debe distinguir qué existe actualmente, qué funciona, qué falta, qué propuesta se recomienda y qué evidencia del CV o Sobre mí respalda la propuesta.

## Arquitectura

Workspace está dividido en una interfaz React y una API local en FastAPI:

~~~text
React + TypeScript + Vite
          |
          | HTTP
          v
FastAPI
  |-- rutas de empleos, perfiles, favoritos, IA y configuración
  |-- servicios de dominio
  |-- proveedores externos
  |-- parsers y renderizadores de documentos
          |
          v
SQLite local
~~~

La capa de servicios separa la lógica de búsqueda, favoritos, documentos y análisis para evitar que una integración externa controle directamente la interfaz.

La capa de IA utiliza un proveedor abstracto. DeepSeek es el proveedor configurado actualmente, pero la separación permite incorporar otro proveedor sin reescribir todos los servicios.

## Tecnologías

### Frontend

- React.
- TypeScript.
- Vite.
- React Router.
- Three.js.
- CSS con tokens de diseño y estilos responsivos.

### Backend

- Python.
- FastAPI.
- Pydantic.
- HTTPX.
- SQLite.
- FTS5 cuando aplica a búsquedas locales.

### Documentos

- pypdf/PyMuPDF para extracción de PDF.
- python-docx para documentos de Word.
- ReportLab para generación de PDFs.
- Renderizadores propios para documentos profesionales.

### Calidad

- Vitest para pruebas del frontend.
- pytest para pruebas del backend.
- Ruff para validación de Python.
- Scripts de contratos, assets, secretos y SBOM.

## Estructura del repositorio

~~~text
Workspace/
|-- backend/
|   |-- job_orchestrator/
|   |   |-- api.py
|   |   |-- schemas.py
|   |   |-- config.py
|   |   |-- connectors/
|   |   |-- services/
|   |   |-- providers/
|   |   |-- documents.py
|   |   |-- ats_documents.py
|   |   |-- linkedin.py
|   |   |-- storage.py
|   |   +-- main.py
|   |-- tests/
|   |-- pyproject.toml
|   +-- uv.lock
|-- frontend/
|   |-- src/
|   |   |-- app/
|   |   |-- pages/
|   |   |-- components/
|   |   |-- api/
|   |   |-- generated/
|   |   |-- hooks/
|   |   +-- styles/
|   |-- public/
|   |-- package.json
|   +-- vite.config.ts
|-- scripts/
|-- docs/
|-- assets/
|-- package.json
|-- pnpm-lock.yaml
|-- compose.yaml
|-- .env.example
+-- README.md
~~~

La estructura concreta puede evolucionar, pero la separación por dominio debe mantenerse: buscar empleos no debe depender del flujo de IA y los documentos no deben depender de la navegación de React.
## Instalación local

### Requisitos

- Windows para los scripts PowerShell de desarrollo descritos abajo. También se incluye una configuración Docker Compose.
- Node.js 22 o superior.
- pnpm 11.19.0, fijado en package.json.
- Python 3.12 y uv disponibles en PATH.
- Git.
- Una clave de TheirStack para búsqueda de empleos.
- Una clave de DeepSeek para funciones de IA.

### Clonar

~~~powershell
git clone https://github.com/AruHonshou/Workspace.git
cd Workspace
~~~

### Crear configuración local

~~~powershell
Copy-Item .env.example .env
~~~

El archivo .env configura el servicio local. Las claves se introducen en Configuración y se guardan en el almacén de credenciales del sistema; Docker también permite inyectarlas mediante variables de entorno. Nunca publiques secretos ni los incluyas directamente en el código.

### Preparar dependencias

~~~powershell
./scripts/bootstrap.ps1
~~~

### Iniciar desarrollo

~~~powershell
./scripts/dev.ps1
~~~

La aplicación queda disponible normalmente en la URL local que indique el script. El frontend y el backend se ejecutan juntos durante el desarrollo.

## Configuración

Las principales opciones del servicio son:

~~~text
JOB_ORCHESTRATOR_HOST=127.0.0.1
JOB_ORCHESTRATOR_PORT=8765
JOB_ORCHESTRATOR_DATA_DIR=./data
JOB_ORCHESTRATOR_ARTIFACT_DIR=./artifacts
JOB_ORCHESTRATOR_DEEPSEEK_MODEL=deepseek-v4-pro
~~~

Consulta .env.example antes de añadir nuevas variables.

### Buenas prácticas

- Usa claves propias en tu entorno local.
- No subas .env.
- No guardes CV ni PDFs dentro del repositorio.
- No compartas la base de datos local si contiene información personal.
- Revoca cualquier clave que haya sido expuesta accidentalmente.
- No copies datos sensibles en issues públicos.

## Comandos de desarrollo

Los scripts de scripts/ centralizan tareas frecuentes:

~~~powershell
# Preparar o actualizar el entorno
./scripts/bootstrap.ps1

# Ejecutar frontend y backend
./scripts/dev.ps1

# Ejecutar pruebas completas
./scripts/test.ps1

# Ejecutar una comprobación rápida
./scripts/test.ps1 -Quick

# Generar o validar contratos
./scripts/generate-contracts.ps1

# Validar archivos estáticos
./scripts/validate-assets.ps1

# Buscar posibles secretos
./scripts/scan-secrets.ps1

# Generar inventario de dependencias
./scripts/generate-sbom.ps1
~~~

## Privacidad y seguridad

Workspace está pensado para trabajar con información profesional sensible. La aplicación debe seguir estas reglas:

- La base de datos local no debe exponerse públicamente.
- Las claves se almacenan mediante la configuración local y los mecanismos de protección disponibles.
- Los logs no deben escribir claves, tokens, CV completos ni datos de contacto innecesarios.
- Las URLs de vacantes se validan antes de abrirse.
- Los archivos importados deben tener límites de tamaño y tipo.
- Los datos enviados a IA deben limitarse a la operación solicitada.
- La IA no debe recibir secretos de configuración.
- El usuario debe poder exportar o eliminar sus datos locales.

La privacidad local no significa que ningún dato salga del equipo: las búsquedas se envían al proveedor configurado y las funciones de IA envían el contexto necesario al proveedor de IA. La interfaz debe comunicarlo con claridad.

## Pruebas y validación

Antes de publicar cambios conviene ejecutar:

~~~powershell
./scripts/test.ps1
./scripts/validate-assets.ps1
./scripts/scan-secrets.ps1
~~~

Las áreas críticas de prueba son:

- Navegación entre rutas.
- Búsquedas con uno o varios proveedores.
- Caché y deduplicación.
- Errores parciales y timeouts.
- Importación de CV en español e inglés.
- Confirmación de hechos profesionales.
- Análisis de brechas.
- Guías de entrevista.
- Generación y descarga de PDF ATS.
- Importación de un PDF de LinkedIn.
- Favoritos y candidaturas.
- Configuración de proveedores.
- Responsive y accesibilidad.

Las respuestas de IA deben validarse con datos sintéticos y casos conocidos para comprobar que no inventan experiencia ni modifican fechas.
## Estado del proyecto

Este repositorio contiene el Workspace actual. El commit 9d0df78 conserva el estado previo a la limpieza de archivos obsoletos; el repositorio histórico de AmeWork permanece independiente.

La aplicación ya contiene la base funcional de:

- Navegación por módulos.
- Búsqueda laboral.
- Fuentes y normalización de resultados.
- Favoritos.
- Perfiles y documentos.
- Sobre mí.
- Candidaturas.
- Integración de IA.
- Análisis de vacantes.
- Preparación de entrevistas.
- CV ATS.
- Análisis de LinkedIn.
- Landing 3D y workspace interactivo.

La publicación del instalador de Windows se mantiene fuera del alcance actual. Ese empaquetado se realizará en una fase posterior.

## Contribuir

Las contribuciones deben mantener el alcance local-first y la separación de responsabilidades.

Antes de abrir un cambio:

1. Explica qué problema resuelve.
2. Indica qué módulo se ve afectado.
3. Evita incluir secretos o datos personales.
4. Añade o actualiza pruebas.
5. Ejecuta los scripts de validación disponibles.
6. Documenta los cambios de configuración.
7. Comprueba que las rutas existentes no se rompan.

Para una integración nueva de empleos, separa siempre:

- Cliente del proveedor.
- Modelo normalizado de vacante.
- Adaptador de fuente.
- Manejo de errores.
- Pruebas con respuestas reales anonimizadas.

Para una función de IA, define:

- Entrada mínima necesaria.
- Modelo estructurado de salida.
- Validación de evidencia.
- Mensaje de error en español.
- Comportamiento cuando DeepSeek no está configurado o no responde.

## Licencia y activos

Antes de publicar el proyecto como open source, revisa las licencias de:

- Dependencias de frontend y backend.
- Modelos 3D.
- Texturas.
- Fuentes.
- Iconos.
- Plantillas.
- Código de terceros.
- Assets descargados desde repositorios externos.

Los assets que no tengan una licencia compatible deben reemplazarse o documentarse antes de la publicación pública. La intención del proyecto es utilizar una identidad visual propia y mantener avisos de atribución cuando una licencia lo requiera.

