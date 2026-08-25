import type { DeepFitAnalysis, DeepSeekStatus, GraphEvent, Interest, SearchRunSummary, TheirStackStatus } from "../types";

const DEFAULT_API_BASE_URL = "";

export interface ApiConfig {
  baseUrl: string;
  sessionToken?: string;
}

export const apiConfig: ApiConfig = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, ""),
  sessionToken: import.meta.env.VITE_SESSION_TOKEN || undefined,
};

let sessionPromise: Promise<void> | null = null;

function resetSession(): void {
  sessionPromise = null;
}

export function initializeSession(config: ApiConfig = apiConfig): Promise<void> {
  if (config.sessionToken) return Promise.resolve();
  if (!sessionPromise) {
    sessionPromise = fetch(`${config.baseUrl}/api/session`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    }).then((response) => {
      if (!response.ok) throw new ApiError("Unable to establish the local session", response.status);
    }).catch((error) => {
      sessionPromise = null;
      throw error;
    });
  }
  return sessionPromise;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function authHeaders(config: ApiConfig): HeadersInit {
  return config.sessionToken ? { "X-Session-Token": config.sessionToken } : {};
}

async function request<T>(config: ApiConfig, path: string, init: RequestInit = {}, retried = false): Promise<T> {
  await initializeSession(config);
  const headers = new Headers({ Accept: "application/json", ...authHeaders(config), ...init.headers });
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${config.baseUrl}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && !config.sessionToken && !retried) {
    resetSession();
    await initializeSession(config);
    return request<T>(config, path, init, true);
  }
  const contentType = response.headers.get("content-type") ?? "";
  const body = response.status === 204
    ? undefined
    : contentType.includes("application/json")
      ? await response.json()
      : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : null;
    const staleTheirStackBackend = response.status === 404
      && detail === "Not Found"
      && (path.startsWith("/api/settings/theirstack") || path.includes("/more"));
    throw new ApiError(
      staleTheirStackBackend
        ? "El backend abierto es una versión anterior. Reinicia la aplicación para activar TheirStack."
        : detail
        ? detail
        : `Request failed with status ${response.status}`,
      response.status,
      body,
    );
  }
  return body as T;
}

export type SearchRunMode = "replay" | "live";
export type JobSource = "replay" | "manual" | "greenhouse" | "lever" | "ashby" | "himalayas" | "we_work_remotely" | "jobicy" | "remotive" | "remote_ok" | "linkedin" | "indeed" | "glassdoor" | "computrabajo" | "theirstack";

export interface StartSearchInput {
  mode: SearchRunMode;
  profile_id?: string;
  query: string;
  location?: string;
  work_mode?: "remote" | "hybrid" | "any";
  sources: JobSource[];
  source_identifiers: Record<string, string>;
  job_ids?: string[];
  limit?: number;
  use_model?: boolean;
  auto_approve?: boolean;
}

export interface ApprovalDecisionInput {
  decision: string;
  edits?: Record<string, unknown>;
  artifact_version?: number;
  entity_ids?: string[];
}

export interface BackendProfileFact {
  fact_id: string;
  category: string;
  text: string;
  verified: boolean;
  evidence?: string | null;
  source_page?: number | null;
  source_span?: string | null;
  language?: "es" | "en" | null;
}

export interface BackendResumeDocument {
  document_id: string;
  language: "es" | "en";
  filename: string;
  imported_at: string;
  extraction_method: string;
  warnings: string[];
}

export interface BackendProfile {
  profile_id: string;
  name: string;
  summary: string;
  confirmed: boolean;
  facts: BackendProfileFact[];
  resumes?: Partial<Record<"es" | "en", BackendResumeDocument>>;
  preferences?: { desired_titles?: string[]; desired_locations?: string[] };
}

export interface BackendCareerResult {
  job_id: string;
  title: string;
  company: string;
  location: string;
  remote: boolean | null;
  source: string;
  sources?: string[];
  verification_level?: "official" | "authorized_feed" | "manual_portal";
  published_at: string;
  official_apply_url: string;
  apply_url?: string | null;
  apply_url_type?: "company" | "portal";
  provider?: string | null;
  source_portal?: string | null;
  source_url?: string | null;
  description_summary: string;
  requirements: string[];
  fit_summary: {
    score: number;
    level: "high" | "medium" | "low";
    strengths: string[];
    gaps: string[];
    confidence: number;
  };
  freshness_verified: true;
  official_url_verified: true;
}

export interface BackendProfileImport {
  profile: BackendProfile;
  extraction_method: string;
  warnings: string[];
}

export interface BackendRankedJob {
  job: {
    job_id: string;
    company: string;
    title: string;
    location: string;
    remote: boolean | null;
    source: string;
    retrieved_at: string;
    pipeline_status: string;
  };
  score: number;
  eligible: boolean | null;
  reasons: string[];
  gaps: string[];
}

export interface BackendRun extends SearchRunSummary {
  result: {
    profile_id?: string;
    ranked_jobs?: BackendRankedJob[];
    artifact_ids?: string[];
    review?: { approved?: boolean };
    aliases?: string[];
    career_results?: BackendCareerResult[];
    window_started_at?: string;
    window_ended_at?: string;
    provider?: string;
    total_available?: number | null;
    retrieved_count?: number;
    next_page?: number | null;
    can_load_more?: boolean;
    loaded_pages?: number[];
    coverage?: {
      sources_requested?: string[];
      sources_failed?: string[];
      retrieved?: number;
      accepted?: number;
      rejected?: Record<string, number>;
    };
  };
}

export interface BackendPack {
  id: string;
  job_id: string;
  title: string;
  version: number;
  status: string;
  claims_verified: number;
  claims_total: number;
  created_at: string;
}

export interface BackendArtifact {
  artifact_id: string;
  title: string;
  content: string;
  version: number;
  claims: Array<{ text: string; fact_ids: string[] }>;
}

export interface ManualJobInput {
  title: string;
  company: string;
  description: string;
  location?: string;
  remote?: boolean;
  url?: string;
  posted_at?: string;
  source?: JobSource;
}

export const api = {
  initializeSession,

  getDeepSeekSettings(): Promise<DeepSeekStatus> {
    return request(apiConfig, "/api/settings/deepseek");
  },

  saveDeepSeekKey(apiKey: string): Promise<DeepSeekStatus> {
    return request(apiConfig, "/api/settings/deepseek", {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey }),
    });
  },

  deleteDeepSeekKey(): Promise<DeepSeekStatus> {
    return request(apiConfig, "/api/settings/deepseek", { method: "DELETE" });
  },

  getTheirStackSettings(): Promise<TheirStackStatus> {
    return request(apiConfig, "/api/settings/theirstack");
  },

  saveTheirStackKey(apiKey: string): Promise<TheirStackStatus> {
    return request(apiConfig, "/api/settings/theirstack", {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey }),
    });
  },

  deleteTheirStackKey(): Promise<TheirStackStatus> {
    return request(apiConfig, "/api/settings/theirstack", { method: "DELETE" });
  },

  importProfile(
    file: File,
    language?: "es" | "en",
    profileId?: string | null,
  ): Promise<BackendProfileImport> {
    const body = new FormData();
    body.append("file", file);
    const query = new URLSearchParams();
    if (language) query.set("language", language);
    if (profileId) query.set("profile_id", profileId);
    const suffix = query.size ? `?${query.toString()}` : "";
    return request(apiConfig, `/api/profiles/import${suffix}`, { method: "POST", body });
  },

  listProfiles(): Promise<BackendProfile[]> {
    return request(apiConfig, "/api/profiles");
  },

  patchProfileFact(id: string, patch: { text?: string; verified?: boolean }): Promise<BackendProfile> {
    return request(apiConfig, `/api/profile-facts/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },

  confirmProfile(profileId: string): Promise<BackendProfile> {
    return request(apiConfig, `/api/profiles/${encodeURIComponent(profileId)}/confirm`, {
      method: "POST",
    });
  },

  createCareerSearch(profileId: string, role: string): Promise<SearchRunSummary> {
    return request(apiConfig, "/api/career/searches", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId, role }),
    });
  },

  getCareerSearch(runId: string): Promise<BackendRun> {
    return request(apiConfig, `/api/career/searches/${encodeURIComponent(runId)}`);
  },

  loadMoreCareerResults(runId: string, page: number): Promise<BackendRun> {
    return request(apiConfig, `/api/career/searches/${encodeURIComponent(runId)}/more`, {
      method: "POST",
      body: JSON.stringify({ page }),
    });
  },

  getJobAnalysis(jobId: string, profileId: string): Promise<DeepFitAnalysis> {
    return request(apiConfig, `/api/jobs/${encodeURIComponent(jobId)}/analysis?profile_id=${encodeURIComponent(profileId)}`);
  },

  createInterest(jobId: string, profileId: string, runId: string): Promise<Interest> {
    return request(apiConfig, `/api/jobs/${encodeURIComponent(jobId)}/interests`, {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId, run_id: runId }),
    });
  },

  listInterests(profileId?: string): Promise<Interest[]> {
    const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : "";
    return request(apiConfig, `/api/interests${query}`);
  },

  getInterest(interestId: string): Promise<Interest> {
    return request(apiConfig, `/api/interests/${encodeURIComponent(interestId)}`);
  },

  deleteInterest(interestId: string): Promise<void> {
    return request(apiConfig, `/api/interests/${encodeURIComponent(interestId)}`, { method: "DELETE" });
  },

  interviewGuideUrl(interestId: string): string {
    return `${apiConfig.baseUrl}/api/interests/${encodeURIComponent(interestId)}/guide.pdf`;
  },

  createSearchRun(input: StartSearchInput): Promise<SearchRunSummary> {
    return request(apiConfig, "/api/search-runs", {
      method: "POST",
      body: JSON.stringify({ auto_approve: false, ...input }),
    });
  },

  listSearchRuns(): Promise<SearchRunSummary[]> {
    return request(apiConfig, "/api/search-runs");
  },

  getSearchRun(runId: string): Promise<BackendRun> {
    return request(apiConfig, `/api/search-runs/${encodeURIComponent(runId)}`);
  },

  listApplicationPacks(runId?: string): Promise<BackendPack[]> {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return request(apiConfig, `/api/application-packs${query}`);
  },

  getArtifact(artifactId: string): Promise<BackendArtifact> {
    return request(apiConfig, `/api/artifacts/${encodeURIComponent(artifactId)}`);
  },

  createManualJob(input: ManualJobInput): Promise<{ job_id: string }> {
    return request(apiConfig, "/api/jobs/manual", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  cancelRun(runId: string): Promise<unknown> {
    return request(apiConfig, `/api/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
  },

  decideApproval(approvalId: string, input: ApprovalDecisionInput): Promise<unknown> {
    return request(apiConfig, `/api/approvals/${encodeURIComponent(approvalId)}/decisions`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  exportApplicationPack(packId: string): Promise<{ download_url?: string; artifact_id?: string }> {
    return request(apiConfig, `/api/application-packs/${encodeURIComponent(packId)}/export`, { method: "POST" });
  },

  updateJobPipelineStatus(jobId: string, status: string): Promise<unknown> {
    return request(apiConfig, `/api/jobs/${encodeURIComponent(jobId)}/pipeline-status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },
};

export interface ParsedSseFrame {
  id?: string;
  event?: string;
  data: string;
  retry?: number;
}

function recordOrEmpty(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

/**
 * Keeps the UI compatible with older event producers while preserving the
 * versioned envelope. Unknown fields are intentionally ignored here and stay
 * available to newer clients through payload/template arguments.
 */
export function normalizeGraphEvent(value: unknown): GraphEvent {
  const raw = recordOrEmpty(value);
  const sequence = Number(raw.sequence);
  if (!Number.isFinite(sequence)) throw new Error("Graph event is missing a numeric sequence");

  const rawUi = recordOrEmpty(raw.ui);
  const rawActorKind = String(raw.actor_kind ?? "workflow");
  const actorKind: GraphEvent["actor_kind"] = ["agent", "worker", "workflow", "user"].includes(rawActorKind)
    ? rawActorKind as GraphEvent["actor_kind"]
    : "workflow";
  const rawSeverity = String(rawUi.severity ?? "info");
  const severity = ["info", "success", "warning", "error"].includes(rawSeverity)
    ? rawSeverity as NonNullable<GraphEvent["ui"]["severity"]>
    : "info";

  return {
    schema_version: typeof raw.schema_version === "string" || typeof raw.schema_version === "number"
      ? raw.schema_version
      : 1,
    event_id: String(raw.event_id ?? `event-${sequence}`),
    run_id: String(raw.run_id ?? "unknown-run"),
    sequence,
    timestamp: String(raw.timestamp ?? new Date(0).toISOString()),
    type: String(raw.type ?? "event"),
    stage: String(raw.stage ?? "unknown"),
    actor_kind: actorKind,
    actor_id: String(raw.actor_id ?? "workflow"),
    target_id: raw.target_id == null ? undefined : String(raw.target_id),
    entity_ref: raw.entity_ref == null ? undefined : String(raw.entity_ref),
    causation_id: raw.causation_id == null ? undefined : String(raw.causation_id),
    payload: recordOrEmpty(raw.payload),
    visibility: raw.visibility === "debug" ? "debug" : "user",
    ui: {
      template_key: String(rawUi.template_key ?? "event.generic"),
      template_args: recordOrEmpty(rawUi.template_args) as GraphEvent["ui"]["template_args"],
      severity,
      progress: typeof rawUi.progress === "number" ? rawUi.progress : undefined,
    },
  };
}

export function parseSseFrame(frame: string): ParsedSseFrame | null {
  const message: ParsedSseFrame = { data: "" };
  const data: string[] = [];
  for (const rawLine of frame.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(":")) continue;
    const separator = rawLine.indexOf(":");
    const field = separator === -1 ? rawLine : rawLine.slice(0, separator);
    const value = separator === -1 ? "" : rawLine.slice(separator + 1).replace(/^ /, "");
    if (field === "data") data.push(value);
    else if (field === "id") message.id = value;
    else if (field === "event") message.event = value;
    else if (field === "retry" && /^\d+$/.test(value)) message.retry = Number(value);
  }
  if (data.length === 0) return null;
  message.data = data.join("\n");
  return message;
}

export type StreamConnectionState = "connecting" | "open" | "reconnecting" | "closed" | "error";

export interface RunEventHandlers {
  onEvent: (event: GraphEvent) => void;
  onStatus?: (status: StreamConnectionState) => void;
  onError?: (error: Error) => void;
}

export class RunEventStream {
  private stopped = true;
  private controller: AbortController | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private lastSequence = 0;
  private retryDelay = 750;

  constructor(private readonly config: ApiConfig = apiConfig) {}

  start(runId: string, handlers: RunEventHandlers): () => void {
    this.stop();
    this.stopped = false;
    this.lastSequence = 0;
    this.retryDelay = 750;
    void this.connect(runId, handlers, false);
    return () => this.stop();
  }

  stop(): void {
    this.stopped = true;
    this.controller?.abort();
    this.controller = null;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
  }

  private scheduleReconnect(runId: string, handlers: RunEventHandlers): void {
    if (this.stopped) return;
    handlers.onStatus?.("reconnecting");
    const delay = this.retryDelay;
    this.retryDelay = Math.min(Math.round(this.retryDelay * 1.8), 15_000);
    this.retryTimer = setTimeout(() => void this.connect(runId, handlers, true), delay);
  }

  private async connect(runId: string, handlers: RunEventHandlers, reconnecting: boolean): Promise<void> {
    if (this.stopped) return;
    handlers.onStatus?.(reconnecting ? "reconnecting" : "connecting");
    this.controller = new AbortController();
    try {
      await initializeSession(this.config);
      const url = new URL(
        `${this.config.baseUrl}/api/runs/${encodeURIComponent(runId)}/events`,
        window.location.origin,
      );
      if (this.lastSequence > 0) url.searchParams.set("after_sequence", String(this.lastSequence));
      const response = await fetch(url, {
        headers: {
          Accept: "text/event-stream",
          ...(this.lastSequence > 0 ? { "Last-Event-ID": String(this.lastSequence) } : {}),
          ...authHeaders(this.config),
        },
        signal: this.controller.signal,
        cache: "no-store",
        credentials: "include",
      });
      if (response.status === 401 && !this.config.sessionToken) resetSession();
      if (!response.ok || !response.body) {
        throw new ApiError(`Event stream failed with status ${response.status}`, response.status);
      }
      handlers.onStatus?.("open");
      this.retryDelay = 750;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let terminal = false;
      while (!this.stopped) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const parsed = parseSseFrame(frame);
          if (!parsed) continue;
          const event = normalizeGraphEvent(JSON.parse(parsed.data));
          if (event.run_id !== runId) throw new Error("Event belongs to a different run");
          if (Number(event.schema_version) !== 1) throw new Error("Unsupported event schema version");
          if (event.sequence <= this.lastSequence) continue;
          if (this.lastSequence > 0 && event.sequence !== this.lastSequence + 1) {
            this.lastSequence = 0;
            throw new Error("Event sequence gap; requesting a full replay");
          }
          this.lastSequence = event.sequence;
          handlers.onEvent(event);
          if (["run_completed", "run_failed", "run_cancelled"].includes(event.type)) {
            terminal = true;
          }
          if (parsed.retry) this.retryDelay = Math.min(parsed.retry, 15_000);
        }
        if (done) break;
      }
      if (terminal) {
        this.stopped = true;
        handlers.onStatus?.("closed");
      } else if (!this.stopped) {
        this.scheduleReconnect(runId, handlers);
      }
    } catch (error) {
      if (this.stopped || (error instanceof DOMException && error.name === "AbortError")) return;
      const normalized = error instanceof Error ? error : new Error(String(error));
      handlers.onError?.(normalized);
      handlers.onStatus?.("error");
      this.scheduleReconnect(runId, handlers);
    }
  }
}
