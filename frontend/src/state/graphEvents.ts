import { AGENT_IDS, type AgentId, type AgentRuntimeState, type ApprovalRequest, type DerivedGraphState, type GraphEvent } from "../types";

function blankAgent(): AgentRuntimeState {
  return { status: "idle", workers: [] };
}

export function initialGraphState(): DerivedGraphState {
  return {
    runId: null,
    runState: "idle",
    stage: "profile",
    agents: Object.fromEntries(AGENT_IDS.map((id) => [id, blankAgent()])) as Record<AgentId, AgentRuntimeState>,
    pendingApproval: null,
    artifacts: [],
    pipelineByJob: {},
    eventsApplied: 0,
    lastSequence: 0,
  };
}

function isAgentId(value: string): value is AgentId {
  return (AGENT_IDS as readonly string[]).includes(value);
}

function messageFrom(event: GraphEvent): Pick<AgentRuntimeState, "lastMessageKey" | "lastMessageArgs" | "progress"> {
  return {
    lastMessageKey: event.ui?.template_key,
    lastMessageArgs: event.ui?.template_args,
    progress: event.ui?.progress ?? (typeof event.payload.progress === "number" ? event.payload.progress : undefined),
  };
}

function patchAgent(
  state: DerivedGraphState,
  id: string,
  patch: Partial<AgentRuntimeState>,
): void {
  if (!isAgentId(id)) return;
  state.agents[id] = { ...state.agents[id], ...patch };
}

function cloneState(state: DerivedGraphState): DerivedGraphState {
  return {
    ...state,
    agents: Object.fromEntries(
      AGENT_IDS.map((id) => [id, { ...state.agents[id], workers: [...state.agents[id].workers] }]),
    ) as Record<AgentId, AgentRuntimeState>,
    artifacts: [...state.artifacts],
    pipelineByJob: { ...state.pipelineByJob },
  };
}

export function applyGraphEvent(previous: DerivedGraphState, event: GraphEvent): DerivedGraphState {
  if (event.sequence <= previous.lastSequence) return previous;
  const state = cloneState(previous);
  state.runId = event.run_id;
  state.stage = event.stage || state.stage;
  state.lastSequence = event.sequence;
  state.eventsApplied += 1;

  switch (event.type) {
    case "run_started":
      state.runState = "running";
      break;
    case "stage_entered":
      state.runState = state.runState === "idle" ? "running" : state.runState;
      break;
    case "task_dispatched":
      if (event.target_id) patchAgent(state, event.target_id, { status: "queued", ...messageFrom(event) });
      break;
    case "agent_started":
      patchAgent(state, event.actor_id, { status: "working", error: undefined, ...messageFrom(event) });
      state.runState = "running";
      break;
    case "agent_progress":
      patchAgent(state, event.actor_id, { status: "working", ...messageFrom(event) });
      break;
    case "agent_completed":
      patchAgent(state, event.actor_id, { status: "completed", progress: 1, ...messageFrom(event) });
      break;
    case "agent_failed":
      patchAgent(state, event.actor_id, {
        status: "error",
        error: String(event.payload.error ?? "Unknown agent error"),
        ...messageFrom(event),
      });
      state.lastError = String(event.payload.error ?? "Unknown agent error");
      break;
    case "fanout_started": {
      const rawWorkers = Array.isArray(event.payload.workers) ? event.payload.workers : [];
      patchAgent(state, event.actor_id, {
        status: "waiting_for_workers",
        workers: rawWorkers.map((value, index) => {
          const worker = value as Record<string, unknown>;
          return {
            id: String(worker.id ?? `worker-${index}`),
            label: String(worker.label ?? `Worker ${index + 1}`),
            status: "queued" as const,
          };
        }),
        ...messageFrom(event),
      });
      break;
    }
    case "worker_started":
    case "worker_completed": {
      const parent = String(event.payload.parent_agent_id ?? "");
      if (isAgentId(parent)) {
        const current = state.agents[parent];
        const exists = current.workers.some((worker) => worker.id === event.actor_id);
        const worker = {
          id: event.actor_id,
          label: String(event.payload.label ?? event.actor_id),
          status: event.type === "worker_started" ? ("working" as const) : ("completed" as const),
        };
        state.agents[parent] = {
          ...current,
          status: "waiting_for_workers",
          workers: exists
            ? current.workers.map((item) => (item.id === event.actor_id ? { ...item, status: worker.status } : item))
            : [...current.workers, worker],
          ...messageFrom(event),
        };
      }
      break;
    }
    case "fanout_completed":
      patchAgent(state, event.actor_id, {
        status: "working",
        workers: state.agents[isAgentId(event.actor_id) ? event.actor_id : "career_coordinator"].workers.map((worker) => ({ ...worker, status: "completed" })),
        progress: 1,
        ...messageFrom(event),
      });
      break;
    case "artifact_created": {
      const artifact = event.payload.artifact as Record<string, unknown> | undefined;
      if (artifact) {
        state.artifacts.push({
          id: String(artifact.id ?? event.event_id),
          kind: String(artifact.kind ?? "artifact"),
          title: String(artifact.title ?? "Artifact"),
          version: typeof artifact.version === "number" ? artifact.version : undefined,
          entityRef: event.entity_ref ?? undefined,
        });
      }
      break;
    }
    case "revision_requested":
      patchAgent(state, "quality_reviewer", { status: "completed", ...messageFrom(event) });
      patchAgent(state, event.target_id ?? "application_tailor", { status: "queued" });
      break;
    case "approval_requested": {
      const approval = event.payload.approval as ApprovalRequest | undefined;
      state.pendingApproval = approval ?? null;
      state.runState = "awaiting_user";
      patchAgent(state, approval?.owner_agent_id ?? "career_coordinator", {
        status: "waiting_for_approval",
        ...messageFrom(event),
      });
      break;
    }
    case "approval_resolved":
      state.pendingApproval = null;
      state.runState = "resuming";
      patchAgent(state, "career_coordinator", { status: "working", ...messageFrom(event) });
      break;
    case "pipeline_status_changed": {
      const jobId = String(event.payload.job_id ?? event.entity_ref ?? "");
      const status = String(event.payload.status ?? "");
      if (jobId && status) state.pipelineByJob[jobId] = status;
      break;
    }
    case "run_completed":
      state.runState = "completed";
      state.stage = "complete";
      break;
    case "run_failed":
      state.runState = "failed";
      state.lastError = String(event.payload.error ?? "Run failed");
      break;
    case "run_cancelled":
      state.runState = "cancelled";
      break;
    default:
      break;
  }

  return state;
}

export function reduceGraphEvents(events: GraphEvent[]): DerivedGraphState {
  const deduped = new Map<string, GraphEvent>();
  for (const event of events) deduped.set(event.event_id, event);
  return [...deduped.values()]
    .sort((left, right) => left.sequence - right.sequence)
    .reduce(applyGraphEvent, initialGraphState());
}
