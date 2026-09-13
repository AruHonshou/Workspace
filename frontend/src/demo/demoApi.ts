const NOW = "2026-09-13T18:30:00Z";
const PROFILE_ID = "demo_profile_qa";
const SEARCH_ID = "demo_search_cr";
const SAVED_ID = "demo_saved_qa";

const profile = {
  profile_id: PROFILE_ID,
  display_name: "QA Automation",
  name: "Sofía Ramírez",
  summary: "QA Automation Engineer | Playwright · TypeScript · API Testing",
  revision: 3,
  confirmed: true,
  facts: [
    { fact_id: "demo_fact_1", category: "experience", text: "Diseñó y mantuvo pruebas end-to-end con Playwright y TypeScript para flujos críticos de comercio electrónico.", verified: true, evidence: "CV en español", source_page: 1, language: "es" },
    { fact_id: "demo_fact_2", category: "achievement", text: "Redujo en un 35% el tiempo de regresión mediante automatización integrada en CI.", verified: true, evidence: "CV en español", source_page: 1, language: "es" },
    { fact_id: "demo_fact_3", category: "skill", text: "Playwright, TypeScript, Postman, REST APIs, SQL, GitHub Actions y metodologías ágiles.", verified: true, evidence: "CV en español", source_page: 2, language: "es" },
    { fact_id: "demo_fact_4", category: "education", text: "Bachillerato en Ingeniería de Software.", verified: true, evidence: "CV en español", source_page: 2, language: "es" },
  ],
  resumes: {
    es: { document_id: "demo_resume_es", language: "es", filename: "CV_QA_ES.pdf", imported_at: NOW, extraction_method: "pdf", warnings: [] },
    en: { document_id: "demo_resume_en", language: "en", filename: "QA_Resume_EN.pdf", imported_at: NOW, extraction_method: "pdf", warnings: [] },
  },
  redacted_preview: {
    preview_id: "demo_preview",
    profile_revision: 3,
    language: "es",
    redacted_text: "QA Automation Engineer con experiencia verificable en Playwright, TypeScript, pruebas API y CI. Reducción confirmada del 35% en tiempo de regresión.",
    redacted_categories: ["email", "phone"],
    content_hash: "demo",
  },
  cloud_processing_consent: {
    status: "granted",
    profile_revision: 3,
    preview_id: "demo_preview",
    purposes: ["fit_analysis", "document_generation"],
  },
  preferences: {
    desired_titles: ["QA Automation Engineer", "SDET"],
    target_seniorities: ["mid", "senior"],
    allowed_work_modes: ["remote", "hybrid"],
    desired_locations: ["Costa Rica", "Remote"],
    excluded_keywords: [],
    excluded_sectors: [],
  },
};

const searchJobs = [
  {
    job_id: "demo_job_qa",
    title: "QA Automation Engineer",
    company: "Nébula Digital",
    location: "San José, Costa Rica · Híbrido",
    description: "Únete al equipo de calidad para diseñar automatización web y API con Playwright, TypeScript y CI/CD. Trabajarás con producto y desarrollo para mejorar la confiabilidad de cada entrega.",
    published_at: "2026-09-12T14:00:00Z",
    date_precision: "timestamp",
    url: "https://www.linkedin.com/jobs/",
    apply_url_type: "portal",
    source_portal: "LinkedIn",
    source_portals: ["LinkedIn", "Indeed"],
    source_urls: ["https://www.linkedin.com/jobs/"],
  },
  {
    job_id: "demo_job_backend",
    title: "Backend Developer · Node.js",
    company: "Bosque Labs",
    location: "Costa Rica · Remoto",
    description: "Desarrollo de APIs REST con Node.js, PostgreSQL y Docker. Buscamos colaboración, calidad de código y experiencia construyendo servicios confiables.",
    published_at: "2026-09-11T16:30:00Z",
    date_precision: "timestamp",
    url: "https://www.indeed.com/",
    apply_url_type: "portal",
    source_portal: "Indeed",
    source_portals: ["Indeed"],
    source_urls: ["https://www.indeed.com/"],
  },
  {
    job_id: "demo_job_support",
    title: "Software Quality Analyst",
    company: "Café Cloud",
    location: "Heredia, Costa Rica",
    description: "Ejecución de pruebas funcionales, documentación de defectos y validación de APIs. Se valora conocimiento de SQL, Postman y automatización.",
    published_at: "2026-09-10T10:15:00Z",
    date_precision: "timestamp",
    url: "https://www.computrabajo.co.cr/",
    apply_url_type: "portal",
    source_portal: "Computrabajo",
    source_portals: ["Computrabajo"],
    source_urls: ["https://www.computrabajo.co.cr/"],
  },
] as const;

let savedJobs = [
  {
    saved_id: SAVED_ID,
    job_id: "demo_job_qa",
    search_id: SEARCH_ID,
    title: "QA Automation Engineer",
    company: "Nébula Digital",
    location: "San José, Costa Rica · Híbrido",
    description: "Buscamos una persona que diseñe y mantenga automatización web y API con Playwright, TypeScript y CI/CD. Colaborará con producto y desarrollo, analizará fallos y fortalecerá la estrategia de calidad.",
    apply_url: "https://www.linkedin.com/jobs/",
    apply_url_type: "portal",
    source_portals: ["LinkedIn", "Indeed"],
    source_urls: ["https://www.linkedin.com/jobs/"],
    published_at: "2026-09-12T14:00:00Z",
    created_at: NOW,
    updated_at: NOW,
  },
  {
    saved_id: "demo_saved_backend",
    job_id: "demo_job_backend",
    search_id: SEARCH_ID,
    title: "Backend Developer · Node.js",
    company: "Bosque Labs",
    location: "Costa Rica · Remoto",
    description: "Construcción de APIs REST con Node.js, PostgreSQL y Docker en un equipo de producto distribuido.",
    apply_url: "https://www.indeed.com/",
    apply_url_type: "portal",
    source_portals: ["Indeed"],
    source_urls: ["https://www.indeed.com/"],
    published_at: "2026-09-11T16:30:00Z",
    created_at: "2026-09-12T09:00:00Z",
    updated_at: "2026-09-12T09:00:00Z",
  },
];

const analysis = {
  analysis_id: "demo_analysis",
  analysis_language: "es",
  confidence: 0.91,
  executive_summary: "El perfil presenta un encaje sólido en automatización web, TypeScript, validación de APIs y CI. La principal brecha es la ausencia de evidencia explícita sobre pruebas de rendimiento.",
  integrity_notice: "Resultado demostrativo basado únicamente en evidencia ficticia confirmada.",
  job_id: "demo_job_qa",
  level: "high",
  profile_id: PROFILE_ID,
  profile_revision: 3,
  resume_language: "es",
  score: 86,
  supported_keywords: ["Playwright", "TypeScript", "API Testing", "CI/CD"],
  missing_technologies: ["k6"],
  priority_gaps: ["No existe evidencia confirmada de pruebas de rendimiento con k6 o una herramienta equivalente."],
  transferable_strengths: ["Automatización de regresión", "Colaboración con desarrollo", "Validación de APIs"],
  cv_actions: ["Destacar el impacto cuantificado de la automatización.", "Relacionar la experiencia en CI con la frecuencia de entregas."],
  uncertainties: [],
  requirement_analysis: [
    { requirement: "Automatización con Playwright y TypeScript", category: "technology", priority: "required", status: "supported", fact_ids: ["demo_fact_1"], evidence: ["Diseñó pruebas end-to-end con Playwright y TypeScript."], explanation: "La evidencia coincide directamente con el requisito." },
    { requirement: "Integración continua", category: "technology", priority: "required", status: "supported", fact_ids: ["demo_fact_2"], evidence: ["Automatización integrada en CI con una reducción del 35%."], explanation: "Existe experiencia verificable y un resultado medible." },
    { requirement: "Pruebas de rendimiento", category: "technology", priority: "preferred", status: "gap", fact_ids: [], evidence: [], explanation: "No aparece evidencia confirmada en el perfil seleccionado." },
  ],
};

const atsResume = {
  version_id: "demo_ats_version",
  resume_id: "demo_ats",
  saved_id: SAVED_ID,
  version: 1,
  language: "es",
  status: "awaiting_approval",
  profile_revision: 3,
  created_at: NOW,
  review_issues: [],
  document: {
    language: "es",
    headline: "QA Automation Engineer | Playwright · TypeScript · API Testing",
    professional_summary: "Ingeniera de calidad especializada en automatización web y validación de APIs, con experiencia integrando pruebas en CI y reduciendo el tiempo de regresión en un 35%.",
    skills: ["Playwright", "TypeScript", "Postman", "REST APIs", "SQL", "GitHub Actions", "CI/CD"],
    experience: [{ record_ids: ["demo_fact_1", "demo_fact_2"], original_text: "Diseñó pruebas end-to-end y redujo el tiempo de regresión.", proposed_text: "Diseñó y mantuvo una suite end-to-end con Playwright y TypeScript, integrada en CI, que redujo en un 35% el tiempo de regresión.", context_heading: "QA Automation Engineer · Experiencia relevante" }],
    projects: [{ record_ids: ["demo_fact_3"], original_text: "Validación de APIs con Postman.", proposed_text: "Construyó colecciones de validación para APIs REST con Postman y SQL, fortaleciendo la detección temprana de defectos.", context_heading: "Proyecto de calidad de APIs" }],
    education: [{ record_ids: ["demo_fact_4"], original_text: "Bachillerato en Ingeniería de Software.", proposed_text: "Bachillerato en Ingeniería de Software", context_heading: "Educación" }],
    certifications: [],
    languages: [{ record_ids: [], original_text: "Español nativo · Inglés B2", proposed_text: "Español — Nativo | Inglés — B2", context_heading: "Idiomas" }],
  },
};

const guide = {
  guide_id: "demo_guide",
  saved_id: SAVED_ID,
  profile_id: PROFILE_ID,
  job_id: "demo_job_qa",
  search_id: SEARCH_ID,
  job_title: "QA Automation Engineer",
  company: "Nébula Digital",
  apply_url: "https://www.linkedin.com/jobs/",
  published_at: "2026-09-12T14:00:00Z",
  analysis,
  document_id: "demo_guide_pdf",
  pdf_path: null,
  language: "es",
  status: "ready",
  version: 1,
  profile_revision: 3,
  is_outdated: false,
  error: null,
  created_at: NOW,
  updated_at: NOW,
};

const aboutMe = {
  dossier_id: "demo_dossier",
  contact: { full_name: "Sofía Ramírez", emails: ["sofia@example.com"], phones: ["+506 0000-0000"], address_lines: [], city: "San José", region: "San José", country_code: "CR", postal_code: "", websites: ["https://example.com/portfolio"], legacy_values: [] },
  entries: [
    { entry_id: "demo_about_1", category: "project", title: "Framework de automatización", details: "Arquitectura de pruebas con Playwright, TypeScript, reportes y ejecución en GitHub Actions.", language: "es", profile_ids: [PROFILE_ID], url: "https://example.com/project", verified: true, created_at: NOW, updated_at: NOW },
    { entry_id: "demo_about_2", category: "certification", title: "ISTQB Foundation", details: "Fundamentos de pruebas, diseño de casos y gestión de defectos.", language: "es", profile_ids: [PROFILE_ID], url: null, verified: true, created_at: NOW, updated_at: NOW },
  ],
  revision: 2,
  updated_at: NOW,
};

let applications = [{
  application_id: "demo_application",
  saved_id: SAVED_ID,
  profile_id: PROFILE_ID,
  job_id: "demo_job_qa",
  title: "QA Automation Engineer",
  company: "Nébula Digital",
  location: "San José, Costa Rica · Híbrido",
  apply_url: "https://www.linkedin.com/jobs/",
  status: "interview",
  notes: "Entrevista técnica programada. Repasar diseño de fixtures, API testing y estrategia de CI.",
  events: [
    { event_id: "demo_event_1", status: "applied", note: "Candidatura enviada", created_at: "2026-09-10T14:00:00Z" },
    { event_id: "demo_event_2", status: "contacted", note: "Contacto inicial de reclutamiento", created_at: "2026-09-11T17:30:00Z" },
    { event_id: "demo_event_3", status: "interview", note: "Entrevista técnica coordinada", created_at: NOW },
  ],
  created_at: "2026-09-10T14:00:00Z",
  updated_at: NOW,
}];

const linkedInSnapshot = {
  snapshot_id: "demo_linkedin_snapshot",
  profile_id: PROFILE_ID,
  language: "es",
  sections: {
    headline: "QA Engineer",
    about: "Profesional de calidad con experiencia en pruebas manuales y automatizadas.",
    experience: "QA Engineer — Automatización de pruebas web y validación de APIs.",
    education: "Bachillerato en Ingeniería de Software.",
    skills: "Playwright, TypeScript, Postman, SQL",
    certifications: "ISTQB Foundation",
  },
  created_at: NOW,
  updated_at: NOW,
};

const linkedInOptimization = {
  optimization_id: "demo_linkedin_v1",
  snapshot_id: linkedInSnapshot.snapshot_id,
  version: 1,
  profile_revision: 3,
  language: "es",
  target_roles: ["QA Automation Engineer", "SDET"],
  status: "ready",
  review_issues: [],
  error: null,
  created_at: NOW,
  sections: [
    { section: "headline", current_text: linkedInSnapshot.sections.headline, proposed_text: "QA Automation Engineer | Playwright · TypeScript · API Testing | Calidad integrada en CI/CD", rationale: "Presenta el rol objetivo y las tecnologías confirmadas desde la primera línea.", keywords: ["QA Automation", "Playwright", "TypeScript", "API Testing"], evidence: [profile.facts[0].text, profile.facts[2].text] },
    { section: "about", current_text: linkedInSnapshot.sections.about, proposed_text: "Ayudo a equipos de producto a entregar software confiable mediante automatización clara, mantenible y conectada con el ciclo de desarrollo. Trabajo con Playwright, TypeScript, Postman, SQL y GitHub Actions; en mi experiencia más reciente, la integración de pruebas en CI redujo un 35% el tiempo de regresión. Me interesa aportar como QA Automation Engineer o SDET en equipos que traten la calidad como una responsabilidad compartida.", rationale: "Conecta propuesta de valor, evidencia cuantificada y objetivo profesional.", keywords: ["SDET", "CI/CD", "Quality Engineering"], evidence: [profile.facts[0].text, profile.facts[1].text] },
    { section: "experience", current_text: linkedInSnapshot.sections.experience, proposed_text: "Diseñé y mantuve pruebas end-to-end con Playwright y TypeScript para flujos críticos de comercio electrónico. Integré la regresión automatizada en CI y reduje su tiempo de ejecución en un 35%, colaborando con desarrollo y producto para diagnosticar fallos y acelerar entregas confiables.", rationale: "Transforma tareas en impacto verificable sin añadir experiencia no confirmada.", keywords: ["E2E", "regression", "CI"], evidence: [profile.facts[0].text, profile.facts[1].text] },
    { section: "education", current_text: linkedInSnapshot.sections.education, proposed_text: "Bachillerato en Ingeniería de Software", rationale: "Conserva literalmente la formación confirmada.", keywords: ["Ingeniería de Software"], evidence: [profile.facts[3].text] },
    { section: "skills", current_text: linkedInSnapshot.sections.skills, proposed_text: "Playwright · TypeScript · API Testing · Postman · REST APIs · SQL · GitHub Actions · CI/CD · Pruebas end-to-end · Regression Testing", rationale: "Prioriza habilidades buscables y respaldadas por el perfil.", keywords: ["Playwright", "API Testing", "CI/CD"], evidence: [profile.facts[2].text] },
    { section: "certifications", current_text: linkedInSnapshot.sections.certifications, proposed_text: "ISTQB Foundation — Fundamentos de pruebas, diseño de casos y gestión de defectos", rationale: "Añade contexto útil a la certificación registrada en Sobre mí.", keywords: ["ISTQB"], evidence: [aboutMe.entries[1].details] },
  ],
};

const searchResult = {
  cached: true,
  error: null,
  excluded_count: 1,
  jobs: searchJobs,
  loaded_pages: [1],
  next_page: null,
  search_id: SEARCH_ID,
  started_at: NOW,
  status: "completed",
  total_available: searchJobs.length,
  warnings: ["Demostración visual: estos resultados son ficticios y no consumen créditos."],
};

function copy<T>(value: T): T {
  return value === undefined ? value : JSON.parse(JSON.stringify(value)) as T;
}

function body(init: RequestInit): Record<string, unknown> {
  if (typeof init.body !== "string") return {};
  try { return JSON.parse(init.body) as Record<string, unknown>; }
  catch { return {}; }
}

export async function handleDemoRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const cleanPath = path.split("?", 1)[0];

  if (cleanPath === "/api/countries") return copy([{ code: "CR", name: "Costa Rica" }, { code: "CO", name: "Colombia" }, { code: "MX", name: "México" }, { code: "ES", name: "España" }, { code: "US", name: "Estados Unidos" }]) as T;
  if (cleanPath === "/api/settings/deepseek") return copy({ configured: true, provider: "deepseek", model: "deepseek-chat", last_verified_at: NOW }) as T;
  if (cleanPath === "/api/settings/theirstack") return copy({ configured: true, provider: "theirstack", batch_size: 20, api_credits: 184, last_verified_at: NOW }) as T;
  if (cleanPath === "/api/providers") return copy([{ id: "theirstack", name: "TheirStack", configured: true, enabled: true }, { id: "brete", name: "Brete", configured: true, enabled: true }]) as T;
  if (cleanPath === "/api/providers/coverage") return copy([{ provider: "theirstack", country_code: "CR", estimated_total: 28, available: true, status: "available", note: "Cobertura de demostración", credits_per_result: 1 }]) as T;

  if (cleanPath === "/api/profiles" && method === "GET") return copy([profile]) as T;
  if (cleanPath === "/api/profiles" && method === "POST") return copy({ ...profile, profile_id: "demo_profile_new", display_name: String(body(init).display_name ?? "Nuevo perfil") }) as T;
  if (/^\/api\/profiles\/[^/]+\/duplicate$/.test(cleanPath)) return copy({ ...profile, profile_id: "demo_profile_copy", display_name: `${profile.display_name} · copia` }) as T;
  if (/^\/api\/profiles\/[^/]+\/(confirm|reprocess|cloud-consent)$/.test(cleanPath)) return copy(profile) as T;
  if (/^\/api\/profiles\/[^/]+$/.test(cleanPath) && method === "PATCH") return copy({ ...profile, ...body(init) }) as T;
  if (/^\/api\/profiles\/[^/]+$/.test(cleanPath) && method === "DELETE") return undefined as T;
  if (cleanPath === "/api/profiles/import") return copy({ profile, extraction_method: "demo", warnings: ["Archivo procesado localmente en la demostración."] }) as T;
  if (/^\/api\/profile-facts\/[^/]+$/.test(cleanPath)) return copy(profile) as T;

  if (cleanPath === "/api/searches") return copy(searchResult) as T;
  if (/^\/api\/searches\/[^/]+/.test(cleanPath)) return copy(searchResult) as T;

  if (/^\/api\/saved-jobs\/[^/]+\/analyses$/.test(cleanPath)) return copy(analysis) as T;
  if (/^\/api\/saved-jobs\/[^/]+\/interview-guides/.test(cleanPath)) return copy(guide) as T;
  if (/^\/api\/saved-jobs\/[^/]+\/ats-resumes$/.test(cleanPath)) return copy(method === "GET" ? [atsResume] : atsResume) as T;
  if (/^\/api\/ats-resumes\/[^/]+\/approve$/.test(cleanPath)) return copy({ ...atsResume, status: "ready" }) as T;
  if (cleanPath === "/api/saved-jobs" && method === "GET") return copy(savedJobs) as T;
  if (cleanPath === "/api/saved-jobs" && method === "POST") return copy(savedJobs[0]) as T;
  if (/^\/api\/saved-jobs\/[^/]+$/.test(cleanPath)) {
    const id = decodeURIComponent(cleanPath.split("/").at(-1) ?? "");
    if (method === "DELETE") { savedJobs = savedJobs.filter((item) => item.saved_id !== id); return undefined as T; }
    return copy(savedJobs.find((item) => item.saved_id === id) ?? savedJobs[0]) as T;
  }

  if (cleanPath === "/api/about-me" && method === "GET") return copy(aboutMe) as T;
  if (cleanPath === "/api/about-me" && method === "PUT") return copy({ ...aboutMe, ...body(init), updated_at: new Date().toISOString() }) as T;

  if (cleanPath === "/api/applications" && method === "GET") return copy(applications) as T;
  if (cleanPath === "/api/applications" && method === "POST") return copy(applications[0]) as T;
  if (/^\/api\/applications\/[^/]+$/.test(cleanPath)) {
    const id = decodeURIComponent(cleanPath.split("/").at(-1) ?? "");
    if (method === "DELETE") { applications = applications.filter((item) => item.application_id !== id); return undefined as T; }
    const patch = body(init);
    applications = applications.map((item) => item.application_id === id ? { ...item, ...patch, updated_at: new Date().toISOString() } : item) as typeof applications;
    return copy(applications.find((item) => item.application_id === id) ?? applications[0]) as T;
  }

  if (cleanPath === "/api/linkedin/imports" && method === "GET") return copy([linkedInSnapshot]) as T;
  if (cleanPath === "/api/linkedin/imports" && method === "POST") return copy(linkedInSnapshot) as T;
  if (/^\/api\/linkedin\/imports\/[^/]+\/optimizations$/.test(cleanPath)) return copy([linkedInOptimization]) as T;
  if (/^\/api\/linkedin\/imports\/[^/]+\/optimize$/.test(cleanPath)) return copy(linkedInOptimization) as T;
  if (/^\/api\/linkedin\/imports\/[^/]+\/(sections|reparse)$/.test(cleanPath)) return copy(linkedInSnapshot) as T;

  if (cleanPath === "/api/data/export") return copy({ mode: "demo", message: "La demostración no contiene datos personales." }) as T;
  if (cleanPath === "/api/data" && method === "DELETE") return copy({ deleted: false, mode: "demo" }) as T;

  throw new Error(`Demo route not implemented: ${method} ${path}`);
}
