# Contracts and workflow events

[Español](contracts-and-events.es.md)

Pydantic models in `backend/job_orchestrator/schemas.py` are authoritative for
backend domain data; TypeScript types in `frontend/src/types.ts` are the browser
projection. This document defines the compatibility rules between them. The
runtime OpenAPI document is authoritative for endpoint request/response bodies.

## General conventions

- IDs are opaque strings with a type prefix; clients never parse business
  meaning from them.
- Timestamps are RFC 3339 UTC strings. A missing value is `null`, not an empty
  date.
- Enums are lower-case wire values. Unknown future event types are retained in
  history and safely ignored by older reducers.
- Public schemas reject unexpected fields at the backend boundary. An additive
  optional field is backward compatible; deleting, renaming, or changing
  semantics requires a schema-version change.
- Error responses follow the API's JSON `detail` envelope and never include a
  traceback, prompt, secret, absolute path, or private document.
- The API transmits serialized data only; internal LangGraph state and
  checkpoint objects are not public contracts.

Core domain objects are `Profile`/`ProfileFact`, `JobRecord`, `CareerJobResult`,
`DeepFitAnalysis`, `Interest`, `Artifact`, `Run`, and `GraphEvent`. Every
factual `Claim` must carry the approved `fact_id` values that support it.

## HTTP surface

| Method and path | Purpose | Important invariant |
| --- | --- | --- |
| `GET /health` | Local readiness | Contains no private/configuration data |
| `POST /api/profiles/import` | Import candidate material | Size/type limits; returns opaque IDs |
| `PATCH /api/profile-facts/{id}` | Edit/verify one fact | Changes profile version and invalidates stale approvals |
| `GET/PUT/DELETE /api/settings/deepseek` | Inspect, validate/store, or remove the cloud credential | Never returns or persists the key outside Windows Credential Manager |
| `GET/PUT/DELETE /api/settings/theirstack` | Inspect, validate/store, or remove the search credential | Validation retrieves no jobs and the key is never returned |
| `POST /api/career/searches` | Search one role over the fixed 30-day window | Requires a confirmed profile and configured DeepSeek key |
| `POST /api/career/searches/{id}/more` | Retrieve the next 25-job batch | Consecutive, cached, and idempotent page with no automatic billable retry |
| `GET /api/career/searches/{id}` | Retrieve stored results and coverage | Browser filters never repeat the search or model call |
| `GET /api/jobs/{id}/analysis` | Create deep evidence analysis on demand | Sends only contact-free confirmed facts |
| `POST /api/jobs/{id}/interests` | Save interest and create the interview guide | Idempotent by profile/job; reviewer gates the PDF |
| `GET /api/interests/{id}/guide.pdf` | Download the reviewed interview guide | Never includes credentials or contact data |
| `GET /api/runs/{id}/events` | Ordered SSE stream | Resume with `after_sequence`; user-visible projection only |
| `POST /api/runs/{id}/cancel` | Request cooperative cancellation | Idempotent; no new artifact commit after cancellation |

The optional `X-Session-Token` is read from local environment and must not
appear in URLs, logs, events, or artifacts.

## GraphEvent envelope

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

The backend emits numeric version `1`; clients may accept the legacy string
`"1"` during v1 migration. `sequence` starts at 1 and is unique and strictly
increasing within one run. `event_id` is globally unique. `causation_id` is
optional and supports fan-out/revision tracing; correctness never depends on
the UI reconstructing hidden reasoning.

`ui.template_key` is a localized message identifier, not model-generated text.
`template_args` contains small scalar values. If a v1 event lacks `ui`, the
normalizer supplies:

```json
{"template_key":"event.generic","template_args":{},"severity":"info"}
```

Never put prompts, chain-of-thought, CV text, job descriptions, credentials,
provider payloads, or local paths in `payload` or `ui`.

Events remain available for audit, cancellation, and resume, but the Ame scene
does not turn them into agent conversations, speech bubbles, or agent motion.
The UI displays only functional status, final results, or clear errors.

## Event vocabulary

| Type | Meaning |
| --- | --- |
| `run_started` | One run was accepted and has begun |
| `stage_entered` | Public workflow stage changed |
| `task_dispatched` | Coordinator queued work for a target agent |
| `agent_started`, `agent_progress`, `agent_completed`, `agent_failed` | Visible lifecycle of one role |
| `fanout_started`, `worker_started`, `worker_completed`, `fanout_completed` | Bounded parallel work owned by an agent |
| `artifact_created` | A new immutable artifact version is available |
| `revision_requested` | Reviewer sent a version back with explicit findings |
| `approval_requested`, `approval_resolved` | Human gate opened/closed |
| `pipeline_status_changed` | Local application tracker changed |
| `run_completed`, `run_failed`, `run_cancelled` | Exactly one terminal outcome |

Event type describes what happened; `actor_id` describes who did it. Agent IDs
are `career_coordinator`, `opportunity_scout`, `fit_analyst`,
`application_tailor`, and `quality_reviewer`. A dynamically fanned-out worker is
not a sixth durable agent and identifies its owner in the payload.

## SSE delivery and reconnection

The SSE frame contains the event JSON in `data`, may set `id` to `event_id`, and
may provide a bounded `retry`. On reconnect, the client requests
`after_sequence=<last-applied>`; the server replays persisted events in order
before live events. The reducer deduplicates by event ID and ignores any
sequence less than or equal to the last applied value.

The server must not silently skip a sequence it has committed. A detected gap
causes resync/error rather than fabricating state. Heartbeats, if present, are
SSE comments and do not consume a workflow sequence.

## Approvals and artifacts

Approval kinds are `profile_confirmation`, `shortlist_selection`, and
`application_approval`. A request includes allowed decisions, owning agent,
entity IDs, and the profile/artifact version under review. A decision is
single-use and idempotent. Edits create a new version; an approval of version N
never authorizes N+1.

Artifacts are immutable by `(job_id, profile_id, kind, version)`. A revision
creates a successor with a new ID/version and preserves the claim ledger. The
browser receives an artifact summary until the user explicitly opens or exports
the private content.
