export const AGENT_IDS = [
  "career_coordinator",
  "opportunity_scout",
  "fit_analyst",
  "application_tailor",
  "quality_reviewer",
] as const;

export type AgentId = (typeof AGENT_IDS)[number];
export type Locale = "es" | "en";
export type ViewId = "profile" | "search" | "results" | "interests" | "settings";

export type AgentStatus =
  | "idle"
  | "queued"
  | "working"
  | "waiting_for_workers"
  | "waiting_for_approval"
  | "completed"
  | "blocked"
  | "error";

export type RunState =
  | "idle"
  | "running"
  | "awaiting_user"
  | "resuming"
  | "completed"
  | "failed"
  | "cancelled";

export interface GraphUiHint {
  template_key: string;
  template_args?: Record<string, string | number | boolean>;
  severity?: "info" | "success" | "warning" | "error";
  progress?: number;
}

export interface GraphEvent {
  schema_version: number | string;
  event_id: string;
  run_id: string;
  sequence: number;
  timestamp: string;
  type: string;
  stage: string;
  actor_kind: "agent" | "worker" | "workflow" | "user";
  actor_id: string;
  target_id?: string | null;
  entity_ref?: string | null;
  causation_id?: string | null;
  payload: Record<string, unknown>;
  visibility: "user" | "debug";
  ui: GraphUiHint;
}

export interface WorkerRun {
  id: string;
  label: string;
  status: "queued" | "working" | "completed" | "error";
  progress?: number;
}

export interface AgentRuntimeState {
  status: AgentStatus;
  progress?: number;
  lastMessageKey?: string;
  lastMessageArgs?: Record<string, string | number | boolean>;
  workers: WorkerRun[];
  error?: string;
}

export interface ApprovalRequest {
  approval_id: string;
  kind: "profile_confirmation" | "shortlist_selection" | "application_approval" | "external_action";
  owner_agent_id: AgentId;
  entity_ids: string[];
  artifact_version?: number;
  allowed_decisions: string[];
  summary?: string;
}

export interface ApprovalArtifact {
  id: string;
  title: string;
  content: string;
  version: number;
  claims: Array<{ text: string; fact_ids: string[] }>;
}

export interface ArtifactSummary {
  id: string;
  kind: string;
  title: string;
  version?: number;
  entityRef?: string;
}

export interface DerivedGraphState {
  runId: string | null;
  runState: RunState;
  stage: string;
  agents: Record<AgentId, AgentRuntimeState>;
  pendingApproval: ApprovalRequest | null;
  artifacts: ArtifactSummary[];
  pipelineByJob: Record<string, string>;
  eventsApplied: number;
  lastSequence: number;
  lastError?: string;
}

export interface ProfileFact {
  id: string;
  category: "experience" | "skill" | "education" | "achievement" | "preference";
  text: string;
  verified: boolean;
  evidence?: string | null;
  sourcePage?: number | null;
  sourceSpan?: string | null;
  language?: "es" | "en" | null;
}

export interface ResumeVariant {
  language: "es" | "en";
  filename: string;
  importedAt: string;
  factCount: number;
}

export interface CandidateProfile {
  id: string | null;
  name: string;
  headline: string;
  location: string;
  targetRoles: string[];
  completion: number;
  confirmed: boolean;
  facts: ProfileFact[];
  resumes: Partial<Record<"es" | "en", ResumeVariant>>;
}

export interface JobRecord {
  id: string;
  company: string;
  title: string;
  location: string;
  workMode: "remote" | "hybrid" | "onsite";
  source: string;
  sources: string[];
  verificationLevel: "official" | "authorized_feed" | "manual_portal";
  publishedAt: string;
  officialApplyUrl: string;
  applyUrlType: "company" | "portal";
  provider?: string | null;
  sourcePortal?: string | null;
  sourceUrl?: string | null;
  description: string;
  requirements: string[];
  fitScore: number;
  fitLevel: "high" | "medium" | "low";
  evidence: string[];
  gaps: string[];
}

export interface DeepSeekStatus {
  configured: boolean;
  provider: "deepseek";
  model: string;
  last_verified_at?: string | null;
}

export interface TheirStackStatus {
  configured: boolean;
  provider: "theirstack";
  batch_size: number;
  api_credits?: number | null;
  last_verified_at?: string | null;
}

export interface DeepFitAnalysis {
  job_id: string;
  profile_id: string;
  score: number;
  level: "high" | "medium" | "low";
  resume_language: "es" | "en";
  matched_requirements: Array<{ requirement: string; fact_id: string; evidence: string }>;
  missing_requirements: string[];
  cv_recommendations: string[];
  cautions: string[];
  generated_at: string;
}

export interface Interest {
  interest_id: string;
  profile_id: string;
  job_id: string;
  run_id: string;
  guide_run_id?: string | null;
  job_title: string;
  company: string;
  official_apply_url: string;
  published_at: string;
  analysis: DeepFitAnalysis;
  guide_artifact_id?: string | null;
  guide_language: "es" | "en";
  guide_status: "preparing" | "ready" | "failed";
  guide_error?: string | null;
  created_at: string;
  updated_at: string;
  job?: JobRecord;
}

export interface ApplicationPack {
  id: string;
  jobId: string;
  company: string;
  role: string;
  version: number;
  status: "drafting" | "reviewing" | "needs_revision" | "ready_for_approval" | "approved";
  claimsVerified: number;
  claimsTotal: number;
  updatedAt: string;
}

export interface SearchRunSummary {
  run_id: string;
  status: RunState | string;
  mode?: "replay" | "live" | string;
  profile_id?: string | null;
  created_at?: string;
  query?: string;
  location?: string;
}
