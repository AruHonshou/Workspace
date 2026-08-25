# Contratos y eventos del workflow

[English](contracts-and-events.md)

Los modelos Pydantic de `backend/job_orchestrator/schemas.py` son la autoridad
de dominio; los tipos de `frontend/src/types.ts` son la proyección del
navegador. Este documento fija su compatibilidad. OpenAPI en runtime manda sobre
los bodies de endpoints.

## Convenciones

- IDs opacos con prefijo; el cliente no extrae significado de ellos.
- Fechas RFC 3339 UTC; ausencia es `null`, no fecha vacía.
- Enums en minúscula. Un reducer antiguo conserva/ignora con seguridad eventos
  futuros desconocidos.
- El backend rechaza campos extra. Un campo opcional aditivo es compatible;
  borrar, renombrar o cambiar semántica exige nueva versión.
- El error JSON usa `detail` y nunca traceback, prompt, secreto, ruta absoluta o
  documento privado.
- Estado/checkpoint interno de LangGraph no es contrato público.

Objetos centrales: `Profile`/`ProfileFact`, `JobRecord`, `CareerJobResult`,
`DeepFitAnalysis`, `Interest`, `Artifact`, `Run` y `GraphEvent`. Toda afirmación
factual cita los `fact_id` aprobados que la sustentan.

## Superficie HTTP

| Método y ruta | Uso | Invariante |
| --- | --- | --- |
| `GET /health` | Readiness local | Sin datos privados/configuración |
| `POST /api/profiles/import` | Importar material | Límites y retorno de IDs opacos |
| `PATCH /api/profile-facts/{id}` | Editar/verificar hecho | Nueva versión e invalida approvals viejos |
| `GET/PUT/DELETE /api/settings/deepseek` | Consultar, validar/guardar o borrar credencial | Nunca devuelve ni persiste la clave fuera de Windows Credential Manager |
| `GET/PUT/DELETE /api/settings/theirstack` | Consultar, validar/guardar o borrar credencial de búsqueda | Validación sin recuperar vacantes; nunca devuelve la clave |
| `POST /api/career/searches` | Buscar un rol en la ventana fija de 30 días | Requiere perfil confirmado y clave DeepSeek configurada |
| `POST /api/career/searches/{id}/more` | Recuperar la siguiente tanda de 25 vacantes | Página consecutiva, cacheada e idempotente; sin retry cobrable automático |
| `GET /api/career/searches/{id}` | Recuperar resultados y cobertura | Los filtros del navegador no repiten búsqueda ni llamada al modelo |
| `GET /api/jobs/{id}/analysis` | Crear análisis profundo bajo demanda | Envía sólo hechos confirmados sin contacto |
| `POST /api/jobs/{id}/interests` | Guardar interés y crear guía | Idempotente por perfil/vacante; el revisor controla el PDF |
| `GET /api/interests/{id}/guide.pdf` | Descargar guía revisada | Nunca incluye credenciales ni datos de contacto |
| `GET /api/runs/{id}/events` | SSE ordenado | Reanuda con `after_sequence`; sólo proyección visible |
| `POST /api/runs/{id}/cancel` | Cancelación cooperativa | Idempotente; no confirma artefactos después |

`X-Session-Token`, si existe, sólo viene del entorno y nunca aparece en URL,
log, evento o artefacto.

## Envelope GraphEvent

```json
{
  "schema_version": 1,
  "event_id": "event_opaque",
  "run_id": "run_opaque",
  "sequence": 12,
  "timestamp": "2026-08-17T20:30:00Z",
  "type": "agent_progress",
  "stage": "analysis",
  "actor_kind": "agent",
  "actor_id": "fit_analyst",
  "target_id": null,
  "entity_ref": "job_opaque",
  "causation_id": "event_previous",
  "payload": { "processed": 8, "total": 20 },
  "visibility": "user",
  "ui": {
    "template_key": "analysis.progress",
    "template_args": { "processed": 8, "total": 20 },
    "severity": "info",
    "progress": 0.4
  }
}
```

Backend emite versión numérica `1`; el cliente puede aceptar `"1"` durante la
migración v1. `sequence` empieza en 1, es único y estrictamente creciente por
run. `event_id` es globalmente único. `causation_id` es opcional para fan-out y
revisiones.

`ui.template_key` es una clave localizada, no texto del modelo. Sus argumentos
son escalares pequeños. Si un evento v1 carece de `ui`, el normalizador usa:

```json
{"template_key":"event.generic","template_args":{},"severity":"info"}
```

Nunca incluyas prompts, razonamiento oculto, CV/vacante completos, credenciales,
payload de proveedor ni rutas en `payload` o `ui`.

Los eventos se conservan para auditoría, cancelación y reanudación, pero la
escena de Ame no los convierte en conversaciones, globos o animaciones de
agentes. La interfaz sólo muestra estados funcionales, resultados o errores.

## Vocabulario

| Tipo | Significado |
| --- | --- |
| `run_started` | Run aceptado e iniciado |
| `stage_entered` | Cambio de etapa pública |
| `task_dispatched` | El coordinador encola trabajo |
| `agent_started`, `agent_progress`, `agent_completed`, `agent_failed` | Ciclo visible de un rol |
| `fanout_started`, `worker_started`, `worker_completed`, `fanout_completed` | Paralelismo acotado propiedad de un agente |
| `artifact_created` | Nueva versión inmutable disponible |
| `revision_requested` | Revisor devuelve versión con hallazgos |
| `approval_requested`, `approval_resolved` | Gate humano abierto/cerrado |
| `pipeline_status_changed` | Cambia tracking local |
| `run_completed`, `run_failed`, `run_cancelled` | Un único final |

El tipo dice qué ocurrió y `actor_id` quién. IDs: `career_coordinator`,
`opportunity_scout`, `fit_analyst`, `application_tailor` y `quality_reviewer`.
Un worker dinámico no es un sexto agente persistente y declara a su dueño.

## SSE y reconexión

El frame lleva JSON en `data`, puede usar `id=event_id` y un `retry` acotado. Al
reconectar se pide `after_sequence=<última aplicada>`; el servidor reproduce
eventos persistidos antes de los live. El reducer deduplica por ID e ignora toda
secuencia menor o igual a la aplicada.

El servidor no omite una secuencia confirmada. Un hueco dispara resync/error, no
estado inventado. Heartbeats son comentarios SSE y no consumen secuencia.

## Aprobaciones y artefactos

Tipos: `profile_confirmation`, `shortlist_selection` y
`application_approval`. La solicitud contiene decisiones permitidas, dueño,
entidades y versión revisada. La decisión es single-use e idempotente. Editar
crea otra versión; aprobar N nunca autoriza N+1.

Los artefactos son inmutables por `(job_id, profile_id, kind, version)`. Una
revisión crea sucesor y conserva el ledger. El navegador sólo recibe resumen
hasta que el usuario abre o exporta el contenido privado.
