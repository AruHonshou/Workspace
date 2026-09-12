import type {
  AboutMeProfile,
  ApplicationStatus,
  ATSResumeVersion,
  CountryOption,
  DeepSeekStatus,
  InterviewGuide,
  JobApplication,
  JobRecord,
  LinkedInOptimizationVersion,
  LinkedInSection,
  LinkedInProfileSnapshot,
  ProviderCoverage,
  TheirStackStatus,
} from "../types";

const DEFAULT_API_BASE_URL = "";
import type { components } from "../generated/api";
export type SimpleSearchResult = Required<components["schemas"]["SearchResult"]>;
export type SimpleSearchInput = components["schemas"]["JobSearchInput"];
export type SavedJob = components["schemas"]["SavedJob"];
export type SavedJobCreate = components["schemas"]["SavedJobCreate"];
export type DeepFitAnalysisV2 = components["schemas"]["DeepFitAnalysisV2"];
export type JobSource = "manual" | "linkedin" | "indeed" | "glassdoor" | "computrabajo" | "theirstack" | "brete";

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

export interface BackendProfileFact {
  fact_id: string;
  category: string;
  text: string;
  verified: boolean;
  evidence?: string | null;
  source_page?: number | null;
  source_span?: string | null;
  language?: string | null;
}

export interface BackendResumeDocument {
  document_id: string;
  language: string;
  filename: string;
  imported_at: string;
  extraction_method: string;
  warnings: string[];
}

export interface BackendProfile {
  profile_id: string;
  display_name?: string;
  name: string;
  summary: string;
  revision?: number;
  confirmed: boolean;
  facts: BackendProfileFact[];
  resumes?: Record<string, BackendResumeDocument>;
  redacted_preview?: {
    preview_id: string;
    profile_revision: number;
    language?: string | null;
    redacted_text: string;
    redacted_categories: string[];
    content_hash: string;
  } | null;
  cloud_processing_consent?: {
    status: "pending" | "granted" | "declined" | "revoked";
    profile_revision: number;
    preview_id: string;
    purposes: string[];
  } | null;
  preferences?: {
    desired_titles?: string[];
    desired_locations?: string[];
    target_seniorities?: string[];
    allowed_work_modes?: Array<"remote" | "hybrid" | "onsite">;
    excluded_keywords?: string[];
    excluded_sectors?: string[];
  };
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
  apply_url_type?: "official" | "ats" | "portal" | "company";
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
  profile_id?: string | null;
  compatibility_status?: "compatible" | "review" | "review_separately";
  filter_reasons?: string[];
  warnings?: string[];
  country_code?: string | null;
  remote_eligibility?: "eligible_for_country" | "ineligible" | "unknown" | "worldwide";
}

export interface ProfileUpdateInput {
  display_name?: string;
  preferences?: {
    desired_titles?: string[];
    desired_locations?: string[];
    target_seniorities?: string[];
    allowed_work_modes?: Array<"remote" | "hybrid" | "onsite">;
    excluded_keywords?: string[];
    excluded_sectors?: string[];
  };
}

export interface BackendProfileImport {
  profile: BackendProfile;
  extraction_method: string;
  warnings: string[];
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

export interface CoverageQuery {
  countryCode: string;
  role?: string;
  provider?: "theirstack";
}

function idempotencyHeaders(key?: string): HeadersInit {
  return key ? { "Idempotency-Key": key } : {};
}

function normalizeJob(value: BackendCareerResult): JobRecord {
  const workMode = /\b(hybrid|híbrido|hibrido)\b/i.test(value.location)
    ? "hybrid"
    : value.remote === true || /\b(remote|remoto)\b/i.test(value.location)
      ? "remote"
      : "onsite";
  return {
    id: value.job_id,
    company: value.company,
    title: value.title,
    location: value.location,
    workMode,
    source: value.source,
    sources: value.sources ?? [value.source],
    verificationLevel: value.verification_level ?? "official",
    publishedAt: value.published_at,
    officialApplyUrl: value.apply_url ?? value.official_apply_url,
    applyUrlType: value.apply_url_type === "company" ? "official" : value.apply_url_type ?? "official",
    provider: value.provider,
    sourcePortal: value.source_portal,
    sourceUrl: value.source_url,
    description: value.description_summary,
    requirements: value.requirements,
    fitScore: value.fit_summary.score,
    fitLevel: value.fit_summary.level,
    evidence: value.fit_summary.strengths,
    gaps: value.fit_summary.gaps,
    profileId: value.profile_id ?? null,
    compatibilityStatus: value.compatibility_status === "review" ? "review_separately" : value.compatibility_status ?? "compatible",
    filterReasons: value.filter_reasons ?? [],
    warnings: value.warnings ?? [],
    countryCode: value.country_code ?? null,
    remoteEligibility: value.remote_eligibility ?? "unknown",
  };
}

type RawLinkedInSnapshot = {
  snapshot_id: string;
  profile_id: string;
  language: string;
  sections: Record<string, string>;
  created_at: string;
  updated_at: string;
};

type RawLinkedInOptimization = {
  optimization_id: string;
  snapshot_id: string;
  version: number;
  profile_revision: number;
  language: string;
  target_roles: string[];
  status: LinkedInOptimizationVersion["status"];
  review_issues: string[];
  error?: string | null;
  created_at: string;
  sections: Array<{
    section: LinkedInSection["key"];
    current_text: string;
    proposed_text: string;
    rationale: string;
    keywords: string[];
    evidence?: string[];
  }>;
};

function normalizeLinkedInOptimization(value: RawLinkedInOptimization): LinkedInOptimizationVersion {
  return {
    ...value,
    sections: value.sections.map((section) => ({
      ...section,
      evidence: section.evidence ?? [],
    })),
  };
}

export function applyLinkedInOptimization(snapshot: LinkedInProfileSnapshot, version: LinkedInOptimizationVersion): LinkedInProfileSnapshot {
  const proposals = new Map(version.sections.map((section) => [section.section, section]));
  return {
    ...snapshot,
    language: version.language,
    status: version.status === "ready" ? "ready" : version.status === "failed" ? "failed" : "optimizing",
    error: version.error,
    sections: snapshot.sections.map((section) => ({
      ...section,
      ...(proposals.get(section.key) ?? {}),
      key: section.key,
    })),
  };
}

function normalizeLinkedInSnapshot(value: RawLinkedInSnapshot): LinkedInProfileSnapshot {
  const keys: LinkedInSection["key"][] = ["headline", "about", "experience", "education", "skills", "certifications"];
  return {
    snapshot_id: value.snapshot_id,
    profile_id: value.profile_id,
    language: value.language,
    status: "imported",
    sections: keys.map((key) => ({ key, current_text: value.sections[key] ?? "" })),
    created_at: value.created_at,
    updated_at: value.updated_at,
  };
}

export const api = {
  initializeSession,

  simpleSearch(payload: SimpleSearchInput): Promise<SimpleSearchResult> {
    return request(apiConfig, "/api/searches", { method: "POST", body: JSON.stringify(payload) });
  },
  getSimpleSearch(id: string): Promise<SimpleSearchResult> {
    return request(apiConfig, `/api/searches/${encodeURIComponent(id)}`);
  },
  moreSimpleSearch(id: string, page: number): Promise<SimpleSearchResult> {
    return request(apiConfig, `/api/searches/${encodeURIComponent(id)}/pages/${page}`, { method: "POST" });
  },
  listSavedJobs(): Promise<SavedJob[]> {
    return request(apiConfig, "/api/saved-jobs");
  },
  getSavedJob(savedId: string): Promise<SavedJob> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}`);
  },
  saveSimpleJob(payload: SavedJobCreate): Promise<SavedJob> {
    return request(apiConfig, "/api/saved-jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteSavedJob(savedId: string): Promise<void> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}`, { method: "DELETE" });
  },
  analyzeSavedJob(savedId: string, profileId: string, language: "es" | "en" = "es"): Promise<DeepFitAnalysisV2> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}/analyses?profile_id=${encodeURIComponent(profileId)}&language=${language}`, {
      method: "POST",
      headers: idempotencyHeaders(`saved-analysis:${savedId}:${profileId}`),
    });
  },
  prepareSavedJobGuide(savedId: string, profileId: string): Promise<InterviewGuide> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}/interview-guides?profile_id=${encodeURIComponent(profileId)}`, {
      method: "POST",
      headers: idempotencyHeaders(`saved-guide:${savedId}:${profileId}`),
    });
  },

  getSavedJobGuide(savedId: string, profileId: string): Promise<InterviewGuide> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}/interview-guides/${encodeURIComponent(profileId)}`);
  },

  regenerateSavedJobGuide(savedId: string, profileId: string): Promise<InterviewGuide> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}/interview-guides/${encodeURIComponent(profileId)}/regenerate`, {
      method: "POST",
    });
  },

  savedJobGuideUrl(savedId: string, profileId: string, disposition: "inline" | "attachment" = "attachment"): string {
    return `${apiConfig.baseUrl}/api/saved-jobs/${encodeURIComponent(savedId)}/interview-guides/${encodeURIComponent(profileId)}/document.pdf?disposition=${disposition}`;
  },
  prepareSavedJobResume(savedId: string, profileId: string, regenerate = false): Promise<ATSResumeVersion> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}/ats-resumes?profile_id=${encodeURIComponent(profileId)}${regenerate ? "&regenerate=true" : ""}`, {
      method: "POST",
      headers: idempotencyHeaders(`saved-resume:${savedId}:${profileId}`),
    });
  },
  getSavedJobResumes(savedId: string, profileId: string): Promise<ATSResumeVersion[]> {
    return request(apiConfig, `/api/saved-jobs/${encodeURIComponent(savedId)}/ats-resumes?profile_id=${encodeURIComponent(profileId)}`);
  },

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

  getAboutMe(): Promise<AboutMeProfile> {
    return request(apiConfig, "/api/about-me");
  },

  saveAboutMe(value: Pick<AboutMeProfile, "contact" | "entries">): Promise<AboutMeProfile> {
    return request(apiConfig, "/api/about-me", {
      method: "PUT",
      body: JSON.stringify(value),
    });
  },

  listApplications(): Promise<JobApplication[]> {
    return request(apiConfig, "/api/applications");
  },

  createApplication(savedId: string, profileId: string): Promise<JobApplication> {
    return request(apiConfig, "/api/applications", {
      method: "POST",
      body: JSON.stringify({ saved_id: savedId, profile_id: profileId, status: "applied" }),
    });
  },

  updateApplication(applicationId: string, patch: { status?: ApplicationStatus; notes?: string }): Promise<JobApplication> {
    return request(apiConfig, `/api/applications/${encodeURIComponent(applicationId)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },

  deleteApplication(applicationId: string): Promise<void> {
    return request(apiConfig, `/api/applications/${encodeURIComponent(applicationId)}`, { method: "DELETE" });
  },

  importProfile(
    file: File,
    language?: string,
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

  createProfile(displayName: string): Promise<BackendProfile> {
    return request(apiConfig, "/api/profiles", {
      method: "POST",
      body: JSON.stringify({ display_name: displayName, name: displayName }),
    });
  },

  updateProfile(profileId: string, patch: ProfileUpdateInput): Promise<BackendProfile> {
    return request(apiConfig, `/api/profiles/${encodeURIComponent(profileId)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },

  duplicateProfile(profileId: string): Promise<BackendProfile> {
    return request(apiConfig, `/api/profiles/${encodeURIComponent(profileId)}/duplicate`, {
      method: "POST",
    });
  },

  deleteProfile(profileId: string): Promise<void> {
    return request(apiConfig, `/api/profiles/${encodeURIComponent(profileId)}`, {
      method: "DELETE",
    });
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

  reprocessProfile(profileId: string): Promise<BackendProfile> {
    return request(apiConfig, `/api/profiles/${encodeURIComponent(profileId)}/reprocess`, {
      method: "POST",
    });
  },

  getCloudPreview(profileId: string): Promise<NonNullable<BackendProfile["redacted_preview"]>> {
    return request(apiConfig, `/api/profiles/${encodeURIComponent(profileId)}/cloud-preview`);
  },

  decideCloudConsent(profileId: string, granted: boolean): Promise<BackendProfile> {
    return request(apiConfig, `/api/profiles/${encodeURIComponent(profileId)}/cloud-consent`, {
      method: "POST",
      body: JSON.stringify({
        granted,
        purposes: ["fit_analysis", "document_generation"],
      }),
    });
  },

  listCountries(): Promise<CountryOption[]> {
    return request(apiConfig, "/api/countries");
  },

  listProviders(): Promise<Array<{ id: string; name: string; configured: boolean; enabled: boolean }>> {
    return request(apiConfig, "/api/providers");
  },

  getProviderCoverage(input: CoverageQuery): Promise<ProviderCoverage[]> {
    const query = new URLSearchParams({ country_code: input.countryCode, provider: input.provider ?? "theirstack" });
    if (input.role?.trim()) query.set("role", input.role.trim());
    return request(apiConfig, `/api/providers/coverage?${query.toString()}`);
  },

  approveATSResume(resumeId: string): Promise<ATSResumeVersion> {
    return request(apiConfig, `/api/ats-resumes/${encodeURIComponent(resumeId)}/approve`, {
      method: "PATCH",
      body: JSON.stringify({ approved: true }),
    });
  },

  atsResumeUrl(resumeId: string, format: "pdf" | "docx"): string {
    return `${apiConfig.baseUrl}/api/ats-resumes/${encodeURIComponent(resumeId)}.${format}`;
  },

  async importLinkedIn(file: File, profileId: string, language: string): Promise<LinkedInProfileSnapshot> {
    const body = new FormData();
    body.append("file", file);
    body.append("profile_id", profileId);
    body.append("language", language);
    return normalizeLinkedInSnapshot(await request<RawLinkedInSnapshot>(apiConfig, "/api/linkedin/imports", { method: "POST", body }));
  },

  async importLinkedInText(profileId: string, language: string, text: string): Promise<LinkedInProfileSnapshot> {
    const value = await request<RawLinkedInSnapshot>(apiConfig, "/api/linkedin/imports", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId, language, text }),
    });
    return normalizeLinkedInSnapshot(value);
  },

  async listLinkedInImports(profileId?: string): Promise<LinkedInProfileSnapshot[]> {
    const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : "";
    const values = await request<RawLinkedInSnapshot[]>(apiConfig, `/api/linkedin/imports${query}`);
    return values.map(normalizeLinkedInSnapshot);
  },

  async listLinkedInOptimizations(snapshotId: string): Promise<LinkedInOptimizationVersion[]> {
    const values = await request<RawLinkedInOptimization[]>(apiConfig, `/api/linkedin/imports/${encodeURIComponent(snapshotId)}/optimizations`);
    return values.map(normalizeLinkedInOptimization);
  },

  async updateLinkedInSections(snapshotId: string, sections: LinkedInProfileSnapshot["sections"]): Promise<LinkedInProfileSnapshot> {
    const value = await request<RawLinkedInSnapshot>(apiConfig, `/api/linkedin/imports/${encodeURIComponent(snapshotId)}/sections`, {
      method: "PATCH",
      body: JSON.stringify({ sections: Object.fromEntries(sections.map((section) => [section.key, section.current_text])) }),
    });
    return normalizeLinkedInSnapshot(value);
  },

  async reparseLinkedIn(snapshotId: string): Promise<LinkedInProfileSnapshot> {
    const value = await request<RawLinkedInSnapshot>(apiConfig, `/api/linkedin/imports/${encodeURIComponent(snapshotId)}/reparse`, {
      method: "POST",
    });
    return normalizeLinkedInSnapshot(value);
  },

  async optimizeLinkedIn(snapshot: LinkedInProfileSnapshot, targetRoles: string[], language: string): Promise<{ snapshot: LinkedInProfileSnapshot; version: LinkedInOptimizationVersion }> {
    const value = await request<RawLinkedInOptimization>(apiConfig, `/api/linkedin/imports/${encodeURIComponent(snapshot.snapshot_id)}/optimize`, {
      method: "POST",
      headers: idempotencyHeaders(`linkedin:${snapshot.snapshot_id}:${language}:${targetRoles.join("|")}`),
      body: JSON.stringify({ target_roles: targetRoles, language }),
    });
    const version = normalizeLinkedInOptimization(value);
    return { snapshot: applyLinkedInOptimization(snapshot, version), version };
  },

  exportLocalData(): Promise<Record<string, unknown>> {
    return request(apiConfig, "/api/data/export");
  },

  deleteLocalData(): Promise<Record<string, unknown>> {
    return request(apiConfig, "/api/data", {
      method: "DELETE",
      body: JSON.stringify({ confirmation: "DELETE_ALL_LOCAL_DATA" }),
    });
  },

};
