# Workspace

Tu espacio personal para buscar empleo, preparar candidaturas y mejorar tu perfil profesional.

**Versión estable actual: 1.0.0.** Consulta el [historial de versiones](CHANGELOG.md) para conocer el alcance y las limitaciones del lanzamiento.

Workspace es una aplicación gratuita y de código abierto que ejecutas en tu equipo. Reúne búsqueda de vacantes, perfiles de CV, favoritos, seguimiento de candidaturas y herramientas de inteligencia artificial en una interfaz con pestañas. La entrada es un escritorio 3D interactivo.

**Tú controlas tus datos y utilizas tus propias API keys.** Workspace no cobra por utilizar la aplicación. TheirStack y DeepSeek pueden cobrar por el uso de sus servicios según la cuenta y el plan de cada usuario.

## Qué puedes hacer

| Apartado | Para qué sirve |
| --- | --- |
| Buscar empleos | Buscar por puesto, país, antigüedad y portales; abrir la publicación original y guardar ofertas. |
| Favoritos | Conservar vacantes interesantes y acceder a sus herramientas de preparación. |
| Mi CV | Crear varios perfiles profesionales, importar CV en español e inglés y revisar la información extraída. |
| Sobre mí | Guardar proyectos, estudios, logros, enlaces y experiencia que complementan tus CV. |
| Candidaturas | Registrar a qué puestos postulaste, su estado, notas e historial. |
| LinkedIn | Comparar tu perfil exportado en PDF con tu información profesional y generar textos mejorados. |
| Configuración | Introducir tus API keys, comprobar conexiones y gestionar tus datos locales. |

Workspace abre la publicación original para que tú decidas dónde y cómo postular. El seguimiento de candidaturas es manual; la aplicación no envía solicitudes ni modifica tu cuenta de LinkedIn.

## Un recorrido de ejemplo

1. Entra en **Buscar empleos**, escribe un puesto como QA y selecciona Costa Rica.
2. Elige las publicaciones de los últimos 7 días y los portales que te interesan.
3. Guarda una vacante en **Favoritos**.
4. En **Mi CV**, crea tu perfil QA Automation, importa el CV y revisa los datos extraídos.
5. Abre el favorito y selecciona ese perfil para analizar brechas, preparar una entrevista o generar un CV ATS.
6. Revisa el resultado, abre la oferta original y realiza tu postulación.
7. Registra el avance en **Candidaturas**.

Puedes buscar sin subir un CV y sin configurar DeepSeek. El perfil confirmado se necesita para las herramientas que utilizan tu experiencia profesional.

## Antes de instalar

La instalación de desarrollo descrita aquí utiliza **Windows y PowerShell 7**.

Necesitas tener disponibles en tu terminal:

| Herramienta | Versión / uso |
| --- | --- |
| Git | Descargar y actualizar el proyecto. |
| Node.js | 22 o superior. |
| pnpm | 11.19.0, fijada en el proyecto. |
| Python | 3.12; el script de instalación comprueba esta versión. |
| uv | Instalar el entorno Python desde el archivo de dependencias bloqueadas. |
| Navegador | Un navegador moderno; WebGL permite disfrutar de la escena 3D. |

Puedes comprobar tu entorno con:

~~~powershell
git --version
node --version
pnpm --version
py -3.12 --version
uv --version
~~~

Los scripts no instalan esas herramientas del sistema por ti. Una vez disponibles, sí preparan las dependencias propias del proyecto.

También se incluye Docker Compose como alternativa para ejecutar los servicios. Consulta la sección de Docker más abajo.

## Instalar y ejecutar

### 1. Descargar Workspace

~~~powershell
git clone https://github.com/AruHonshou/Workspace.git
cd Workspace
~~~

### 2. Crear la configuración local

~~~powershell
Copy-Item .env.example .env
~~~

Este paso es para una instalación nueva. Si ya tienes un archivo .env, conserva tu configuración y compara las opciones del ejemplo antes de actualizarlo.

### 3. Instalar las dependencias

~~~powershell
./scripts/bootstrap.ps1
~~~

El script prepara el entorno Python, instala las dependencias del frontend con las versiones fijadas y valida los recursos visuales. Requiere conexión a Internet para descargar los paquetes.

### 4. Iniciar la aplicación

~~~powershell
./scripts/dev.ps1
~~~

Abre **[Workspace en tu equipo](http://127.0.0.1:5173/)**.

El script inicia ambos servicios:

- Interfaz: http://127.0.0.1:5173/
- API local: http://127.0.0.1:8765/

Mantén la terminal abierta mientras lo utilizas. Pulsa Ctrl+C para detener los procesos iniciados por ese script.

En los siguientes usos, abre una terminal en la carpeta del proyecto y ejecuta de nuevo ./scripts/dev.ps1.

## Configurar tus API keys

Entra en **Configuración** y añade tus claves.

### TheirStack: búsqueda de vacantes

TheirStack proporciona resultados procedentes de distintos portales. El selector incluye LinkedIn, Indeed, Computrabajo, Glassdoor, InfoJobs, Naukri y páginas de empresa/ATS. La disponibilidad real depende de la cobertura del proveedor, el país y los filtros.

Para Costa Rica también existe un conector independiente de Brete/ANE que consulta sus páginas públicas.

Ten en cuenta:

- TheirStack es el proveedor de los datos; el portal indicado en cada vacante es su fuente.
- Una consulta puede consumir créditos por los registros recuperados; no debes asumir que una búsqueda equivale a un único crédito.
- Workspace conserva búsquedas en SQLite y utiliza una caché de 30 minutos para consultas equivalentes.
- **Cargar más** o actualizar resultados puede consumir créditos adicionales.
- La deduplicación evita mostrar varias veces una misma oferta, pero no garantiza que el proveedor no cobre por registros que ya entregó.

### DeepSeek: herramientas de IA

DeepSeek se utiliza al solicitar análisis de brechas, preparación de entrevista, CV ATS o propuestas para LinkedIn.

Añade la clave, comprueba la conexión y revisa el contexto y consentimiento solicitados antes de generar contenido. Una clave válida también necesita acceso al modelo configurado y saldo o cuota disponibles.

En la ejecución local, las claves se guardan en el almacén de credenciales del sistema operativo. No se distribuyen con el repositorio.

## Cómo utilizar cada herramienta

### Buscar empleos

Escribe el puesto, elige el país y selecciona la antigüedad: últimas 24 horas, 7 días o 30 días. Ajusta los portales y pulsa **Buscar**.

La búsqueda incluye equivalencias previsibles de algunos roles. Por ejemplo, QA puede ampliarse a QA Engineer, Quality Assurance, Tester y QA Automation. La aplicación agrupa duplicados conservando información de procedencia.

Puedes volver a la última búsqueda mientras siga disponible en tus datos locales. Una búsqueda nueva sustituye los resultados mostrados. Los favoritos se mantienen de forma independiente.

### Mi CV

Crea un perfil por enfoque profesional: QA, desarrollo de software, ciberseguridad u otro. Cada perfil admite documentos en **español e inglés**.

El flujo es **Importar → Revisar → Confirmar**. Corrige la información detectada antes de utilizarla con IA. Un documento con texto seleccionable suele ofrecer mejores resultados de extracción que una imagen escaneada.

Las funciones asociadas a una oferta seleccionan la variante de CV según su idioma. Si falta la variante requerida, la interfaz puede pedirte completarla.

### Sobre mí

Completa la información que no aparece en tus CV: proyectos, responsabilidades, formación, certificaciones, logros y enlaces. Actualízala cuando cambie tu experiencia.

Esta información complementa las herramientas profesionales. Añade únicamente datos que puedas respaldar.

### Favoritos y detalle de una vacante

Desde una vacante guardada puedes abrir su publicación, seleccionar el perfil para documentos y utilizar:

**Analizar brechas:** compara los requisitos con la evidencia del perfil y muestra fortalezas, coincidencias, carencias y aspectos por confirmar. Que una tecnología no aparezca en tu CV significa que no hay evidencia registrada; no demuestra que no la conozcas.

**Preparar entrevista:** genera una guía con contexto del puesto, temas técnicos, preguntas y preparación apoyada en tu experiencia. Puedes consultar y descargar el documento. El idioma depende de la oferta.

**Crear CV ATS:** utiliza el perfil, la vacante y la información adicional para proponer un CV adaptado. Revisa el contenido y las comprobaciones de evidencia, confirma lo que corresponda y descarga el documento mediante las opciones disponibles.

La IA puede reorganizar y mejorar la redacción, pero no debe inventar fechas, experiencia, certificaciones o logros. El formato ATS facilita la lectura automática; no garantiza superar todos los filtros ni conseguir una entrevista.

### Candidaturas

Marca una oferta como postulada y organiza el proceso con sus estados: postulado, contactado, revisión inicial, entrevista, prueba técnica, oferta, contratado o rechazado, según las opciones disponibles.

Registra notas e historial para recordar qué ocurrió en cada proceso. Los cambios de estado dependen de lo que tú registres.

### LinkedIn

1. Exporta tu perfil de LinkedIn como PDF.
2. Selecciona el perfil profesional de **Mi CV**.
3. Elige el idioma de salida: español o inglés.
4. Indica el objetivo de tu perfil.
5. Sube el PDF y revisa su información extraída.
6. Solicita la generación.

Workspace combina el PDF, el perfil seleccionado y los datos de **Sobre mí** para proponer textos para titular, acerca de, experiencia, educación, habilidades y certificaciones.

Revisa las propuestas y copia el texto a LinkedIn. Workspace no necesita acceso a tu cuenta y no publica los cambios por ti.

## Tus datos y privacidad

Cada instalación tiene sus propios perfiles, documentos, favoritos, candidaturas y análisis. Al clonar el proyecto recibes el código y los recursos visuales, no los datos del creador ni sus API keys.

- La base de datos y los documentos se guardan localmente.
- TheirStack recibe los criterios necesarios para buscar.
- DeepSeek recibe el contexto profesional necesario para la operación solicitada, con los filtros y revisión que ofrece la aplicación.
- Ejecutar Workspace localmente no convierte las llamadas a DeepSeek en procesamiento local: el contexto enviado se procesa en ese proveedor.
- Desde Configuración puedes gestionar la exportación y eliminación de datos.

La ubicación depende de la configuración. Con el .env.example copiado, se utilizan ./data y ./artifacts. Sin esa configuración, el backend utiliza .local/job-orchestrator y su subcarpeta artifacts.

Conserva una copia de tus datos antes de mover o reinstalar el proyecto. No publiques bases de datos, CV, archivos .env ni claves.

## Ejecutar con Docker

Necesitas Docker y Docker Compose. Desde la carpeta del proyecto, proporciona las claves mediante variables del entorno y ejecuta:

~~~powershell
docker compose up --build
~~~

Abre http://127.0.0.1:5173/. Los datos se guardan en un volumen persistente. Para detener los servicios:

~~~powershell
docker compose down
~~~

No añadas la opción -v si quieres conservar el volumen con tus datos. Las claves inyectadas mediante el entorno del contenedor son de solo lectura desde la interfaz.

El repositorio incluye esta alternativa; los comandos PowerShell de desarrollo son la ruta utilizada para la validación local de este cambio.

## Actualizar

Detén la aplicación y, desde la carpeta del proyecto:

~~~powershell
git pull --ff-only
./scripts/bootstrap.ps1
./scripts/dev.ps1
~~~

Conserva tu archivo .env, el directorio de datos y el de documentos. Si modificaste el código localmente, revisa esos cambios antes de actualizar.

## Problemas frecuentes

| Problema | Qué comprobar |
| --- | --- |
| No se reconoce Python, uv o pnpm | Instala la herramienta requerida, comprueba su versión y abre una terminal nueva. |
| No puede iniciarse el servidor | Comprueba que no haya otra instancia usando los puertos 5173 o 8765. |
| TheirStack rechaza la búsqueda | Revisa la clave, cuota/saldo, filtros y mensaje del proveedor. |
| No aparecen ofertas | Prueba otro término, amplía la antigüedad o revisa las fuentes y su cobertura. |
| DeepSeek no genera contenido | Revisa conexión, modelo, saldo, perfil confirmado y el consentimiento mostrado. |
| El PDF no se interpreta bien | Comprueba que no esté corrupto o protegido y que contenga texto seleccionable. |
| La escena 3D no carga | La aplicación dispone de una imagen de respaldo; revisa WebGL y la aceleración gráfica. |

Para un diagnóstico local:

~~~powershell
./scripts/diagnose.ps1
~~~

El diagnóstico no muestra tus API keys. Más detalles en [Solución de problemas](docs/troubleshooting.es.md).

## Para desarrolladores

La interfaz utiliza React, TypeScript, Vite, React Router y Three.js. La API está construida con Python, FastAPI, Pydantic y HTTPX. SQLite conserva los datos. Los documentos se procesan con pypdf, python-docx y ReportLab, con dependencias opcionales para OCR.

| Carpeta | Contenido |
| --- | --- |
| frontend/src | Interfaz, páginas, escena, estilos y pruebas del navegador. |
| frontend/public | Fuentes y recursos visuales locales. |
| backend/job_orchestrator | API, modelos, almacenamiento, proveedores y servicios. |
| backend/tests | Pruebas de API, perfiles, documentos, búsqueda e IA. |
| scripts | Instalación, ejecución, diagnóstico y validación. |
| assets | Manifiesto de recursos visuales. |
| docs | Documentación técnica y de operación. |

### Comprobar cambios

~~~powershell
./scripts/test.ps1
./scripts/generate-contracts.ps1
./scripts/validate-assets.ps1
./scripts/scan-secrets.ps1
~~~

Las pruebas utilizan datos sintéticos y proveedores simulados. No requieren tus claves ni consumen créditos reales.

Consulta la [documentación](docs/README.md), la [guía de contribución](CONTRIBUTING.md) y la [política de seguridad](SECURITY.md).

## Creador

Creado por **Kendall Valverde Díaz — AruHonshou**.

- [GitHub](https://github.com/AruHonshou)
- [LinkedIn](https://www.linkedin.com/in/kendall-valverde-diaz-aru/)
- [Portafolio](https://aruhonshou.github.io/Aru/portfolio.html)

Los enlaces de la taza, el ratón y el cuaderno identifican al creador. Permanecen en la aplicación y no se utilizan como datos del perfil profesional de cada usuario.

## Licencia

El código se distribuye bajo [Apache-2.0](LICENSE). Las fuentes y otros componentes de terceros conservan sus licencias; consulta [THIRD_PARTY_ASSETS.md](THIRD_PARTY_ASSETS.md).

Workspace es gratuito. Los costes de servicios externos, si los hubiera, corresponden a las cuentas que configura cada usuario.
