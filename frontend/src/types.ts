export type Locale = "es" | "en";
export type ViewId = "profile" | "about" | "search" | "favorites" | "applications" | "linkedin" | "settings";

export interface ProfileFact {
  id: string;
  category: "experience" | "project" | "skill" | "education" | "certification" | "achievement" | "preference";
  text: string;
  verified: boolean;
  evidence?: string | null;
  sourcePage?: number | null;
  sourceSpan?: string | null;
  language?: string | null;
}

export interface ResumeVariant {
  language: string;
  filename: string;
  importedAt: string;
  factCount: number;
}

export interface CandidateProfile {
  id: string | null;
  displayName: string;
  name: string;
  headline: string;
  location: string;
  targetRoles: string[];
  revision: number;
  completion: number;
  confirmed: boolean;
  facts: ProfileFact[];
  resumes: Record<string, ResumeVariant>;
  preferences: ProfilePreferences;
  redactedPreview?: RedactedProfessionalPreview | null;
  cloudConsent?: CloudProcessingConsent | null;
  cloudConsentValid?: boolean;
}

export interface ProfilePreferences {
  desiredTitles: string[];
  targetSeniorities: string[];
  allowedWorkModes: Array<"remote" | "hybrid" | "onsite">;
  desiredLocations: string[];
  excludedKeywords: string[];
  excludedSectors: string[];
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
  applyUrlType: "official" | "ats" | "portal" | "company";
  provider?: string | null;
  sourcePortal?: string | null;
  sourceUrl?: string | null;
  description: string;
  requirements: string[];
  fitScore: number;
  fitLevel: "high" | "medium" | "low";
  evidence: string[];
  gaps: string[];
  profileId?: string | null;
  compatibilityStatus: "compatible" | "review_separately";
  filterReasons: string[];
  warnings: string[];
  countryCode?: string | null;
  remoteEligibility?: RemoteEligibility;
}

export type WorkMode = "remote" | "hybrid" | "onsite";
export type RemoteEligibility = "eligible_for_country" | "ineligible" | "unknown" | "worldwide";
export type ApplyUrlType = "official" | "ats" | "portal";
export type CompatibilityStatus = "compatible" | "review_separately";

export interface CountryOption {
  code: string;
  name: string;
}

export interface CountrySearchScope {
  profile_id: string;
  role: string;
  country_code: string;
  city_or_region?: string;
  modalities: WorkMode[];
  include_global_remote: boolean;
  paid_provider: "theirstack";
}

export interface ProviderCoverage {
  provider: string;
  country_code: string;
  estimated_total?: number | null;
  available: boolean;
  status: "available" | "limited" | "unavailable" | "unknown";
  note?: string | null;
  credits_per_result?: number | null;
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
  analysis_id?: string;
  job_id: string;
  profile_id: string;
  profile_revision?: number;
  score: number;
  level: "high" | "medium" | "low";
  resume_language: string;
  analysis_language?: Locale;
  executive_summary?: string;
  matched_requirements?: Array<{ requirement: string; fact_id: string; evidence: string }>;
  missing_requirements?: string[];
  cv_recommendations?: string[];
  cautions?: string[];
  requirement_analysis?: Array<{
    requirement: string;
    category: "technology" | "experience" | "education" | "language" | "logistics" | "other";
    priority: "required" | "preferred" | "unknown";
    status: "supported" | "gap" | "unknown";
    fact_ids: string[];
    evidence: string[];
  }>;
  technology_summary?: Array<{ technology: string; status: "supported" | "gap" | "unknown"; fact_ids: string[] }>;
  supported_keywords?: string[];
  priority_gaps?: string[];
  transferable_strengths?: string[];
  cv_actions?: string[];
  missing_technologies?: string[];
  uncertainties?: string[];
  integrity_notice?: string;
  confidence?: number;
  generated_at: string;
}

export interface InterviewGuide {
  guide_id: string;
  saved_id: string;
  profile_id: string;
  job_id: string;
  search_id: string;
  job_title: string;
  company: string;
  apply_url: string;
  published_at: string;
  analysis: DeepFitAnalysis;
  document_id?: string | null;
  pdf_path?: string | null;
  language: string;
  status: "preparing" | "reviewing" | "rendering" | "ready" | "failed";
  version: number;
  template_version?: string;
  profile_revision?: number;
  job_content_hash?: string;
  is_outdated?: boolean;
  error?: string | null;
  created_at: string;
  updated_at: string;
  job?: JobRecord;
}

export type DocumentStatus = "preparing" | "drafting" | "reviewing" | "awaiting_approval" | "approved" | "rendering" | "ready" | "failed";

export interface ATSResumeLine {
  record_ids: string[];
  original_text: string;
  proposed_text: string;
  context_heading?: string | null;
}

export interface ATSResumeDocument {
  language: string;
  headline: string;
  professional_summary: string;
  skills: string[];
  experience: ATSResumeLine[];
  projects: ATSResumeLine[];
  education: ATSResumeLine[];
  certifications: ATSResumeLine[];
  languages: ATSResumeLine[];
}

export interface ATSResumeVersion {
  version_id: string;
  resume_id: string;
  saved_id: string;
  version: number;
  language: string;
  status: DocumentStatus;
  profile_revision: number;
  document?: ATSResumeDocument | null;
  review_issues?: string[];
  created_at: string;
  error?: string | null;
}

export type AboutMeCategory = "experience" | "project" | "skill" | "education" | "certification" | "achievement";

export interface AboutMeEntry {
  entry_id: string;
  category: AboutMeCategory;
  title: string;
  details: string;
  language: Locale;
  profile_ids: string[];
  url?: string | null;
  verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface AboutMeProfile {
  dossier_id: string;
  contact: {
    full_name?: string | null;
    emails: string[];
    phones: string[];
    address_lines: string[];
    city?: string | null;
    region?: string | null;
    country_code?: string | null;
    postal_code?: string | null;
    websites: string[];
    legacy_values?: string[];
  };
  entries: AboutMeEntry[];
  revision: number;
  updated_at: string;
}

export type ApplicationStatus = "applied" | "contacted" | "screening" | "interview" | "technical_test" | "offer" | "hired" | "rejected" | "no_response" | "withdrawn";

export interface JobApplicationEvent {
  event_id: string;
  status: ApplicationStatus;
  note: string;
  created_at: string;
}

export interface JobApplication {
  application_id: string;
  saved_id: string;
  profile_id: string;
  job_id: string;
  title: string;
  company: string;
  location: string;
  apply_url: string;
  status: ApplicationStatus;
  notes: string;
  events: JobApplicationEvent[];
  created_at: string;
  updated_at: string;
}

export interface RedactedProfessionalPreview {
  preview_id: string;
  profile_revision: number;
  language?: string | null;
  redacted_text: string;
  redacted_categories: string[];
  content_hash: string;
}

export interface CloudProcessingConsent {
  status: "pending" | "granted" | "declined" | "revoked";
  profile_revision: number;
  preview_id: string;
  purposes: string[];
}

export type LinkedInSectionKey = "headline" | "about" | "experience" | "education" | "skills" | "certifications";

export interface LinkedInSection {
  key: LinkedInSectionKey;
  current_text: string;
  proposed_text?: string | null;
  rationale?: string | null;
  keywords?: string[];
  evidence?: string[];
  character_count?: number;
}

export interface LinkedInProfileSnapshot {
  snapshot_id: string;
  profile_id: string;
  language: string;
  status: "imported" | "reviewed" | "optimizing" | "ready" | "failed";
  sections: LinkedInSection[];
  created_at: string;
  updated_at: string;
  error?: string | null;
}

export interface LinkedInOptimizationSection {
  section: LinkedInSectionKey;
  current_text: string;
  proposed_text: string;
  rationale: string;
  keywords: string[];
  evidence: string[];
}

export interface LinkedInOptimizationVersion {
  optimization_id: string;
  snapshot_id: string;
  version: number;
  profile_revision: number;
  language: string;
  target_roles: string[];
  sections: LinkedInOptimizationSection[];
  status: DocumentStatus;
  review_issues: string[];
  error?: string | null;
  created_at: string;
}
