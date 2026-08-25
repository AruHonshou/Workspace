# Architecture

[Español](architecture.es.md)

AmeWork uses FastAPI, SQLite, LangGraph, and a React/Three.js UI. The
browser communicates only with FastAPI on localhost through REST and SSE.

The `StateGraph` coordinates five internal roles: coordination, search, fit
analysis, preparation, and review. LangChain creates the agents with
`deepseek-v4-pro`; filtering, deduplication, ranking, time limits, evidence
selection, and PDF rendering remain deterministic.

TheirStack is the primary Costa Rica connector. It retrieves 25 jobs per batch,
caches each page, and preserves provider, source portal, source URL, final URL,
and link type. Greenhouse, Lever, Ashby, Himalayas, We Work Remotely, Jobicy,
Remotive, and Remote OK remain fallbacks. Portals without an authorized
integration can also open for manual import.

Separate DeepSeek and TheirStack keys live in Windows Credential Manager. The backend sends only
confirmed professional facts without contact details, the necessary job text,
and typed JSON contracts. Prompts, reasoning, and secrets never enter SSE.

React renders one scene: Ame's animated terrarium as the visible orchestrator.
The five graph roles are not rendered as avatars or conversations. The scene
supports constrained rotation, zoom, and pan and uses a static SVG fallback when
WebGL or motion is unavailable.
