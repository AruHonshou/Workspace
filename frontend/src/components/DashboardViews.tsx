import React, { useMemo, useState } from "react";
import type { ManualJobInput } from "../api/client";
import type { Translate } from "../i18n";
import type {
  CandidateProfile,
  DeepFitAnalysis,
  DeepSeekStatus,
  Interest,
  JobRecord,
  ProfileFact,
  TheirStackStatus,
} from "../types";

function formatDate(value: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function ProfileView({ profile, t, locale, onImport, onUpdateFact, onConfirm }: {
  profile: CandidateProfile;
  t: Translate;
  locale: "es" | "en";
  onImport: (file: File, language: "es" | "en") => Promise<void>;
  onUpdateFact: (fact: ProfileFact, text: string) => Promise<void>;
  onConfirm: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const grouped = useMemo(() => {
    const order: ProfileFact["category"][] = ["experience", "skill", "education", "achievement", "preference"];
    return order
      .map((category) => ({ category, facts: profile.facts.filter((fact) => fact.category === category) }))
      .filter((group) => group.facts.length);
  }, [profile.facts]);
  const labels: Record<ProfileFact["category"], string> = locale === "es"
    ? { experience: "Experiencia", skill: "Habilidades", education: "Educación", achievement: "Logros", preference: "Preferencias" }
    : { experience: "Experience", skill: "Skills", education: "Education", achievement: "Achievements", preference: "Preferences" };
  const hasBothResumes = Boolean(profile.resumes.es && profile.resumes.en);
  const step = !hasBothResumes ? 1 : profile.confirmed ? 3 : 2;
  const importFile = async (file: File | undefined, language: "es" | "en") => {
    if (!file) return;
    setBusy(true);
    try { await onImport(file, language); } finally { setBusy(false); }
  };

  return (
    <section className="view-section career-profile">
      <div className="view-heading">
        <div>
          <span className="eyebrow">01 · {locale === "es" ? "Tu historia profesional" : "Your professional story"}</span>
          <h2>{t("profile.title")}</h2>
          <p>{locale === "es" ? "Convierte tu CV en hechos verificables. Los agentes sólo podrán usar aquello que confirmes." : "Turn your résumé into verifiable facts. Agents can only use what you confirm."}</p>
        </div>
        <span className={`profile-state ${profile.confirmed ? "confirmed" : "pending"}`}>{profile.confirmed ? t("profile.confirmed") : t("profile.pending")}</span>
      </div>

      <ol className="profile-steps" aria-label={locale === "es" ? "Progreso del CV" : "Résumé progress"}>
        {[locale === "es" ? "Importar" : "Import", locale === "es" ? "Revisar" : "Review", locale === "es" ? "Confirmar" : "Confirm"].map((label, index) => (
          <li key={label} className={step >= index + 1 ? "active" : ""}>
            <span>{step > index + 1 ? "✓" : index + 1}</span><strong>{label}</strong>
          </li>
        ))}
      </ol>

      <div className="resume-language-intro"><strong>{locale === "es" ? "Necesitas las dos versiones" : "Both versions are required"}</strong><span>{locale === "es" ? "Usaremos automáticamente el CV que coincida con el idioma de cada vacante." : "We automatically use the résumé matching each job's language."}</span></div>
      <div className="bilingual-resumes">
        {(["es", "en"] as const).map((language) => {
          const resume = profile.resumes[language];
          const label = language === "es" ? (locale === "es" ? "CV en español" : "Spanish résumé") : (locale === "es" ? "CV en inglés" : "English résumé");
          return <label key={language} className={`resume-language-card ${resume ? "is-ready" : "is-missing"}`}>
            <span className="resume-language-code">{language.toUpperCase()}</span>
            <span className="resume-language-copy"><strong>{label}</strong><small>{resume ? `${resume.filename} · ${resume.factCount} ${locale === "es" ? "hechos" : "facts"}` : (locale === "es" ? "Pendiente de importar" : "Waiting for upload")}</small></span>
            <span className="resume-language-action">{busy ? "…" : resume ? (locale === "es" ? "Reemplazar" : "Replace") : (locale === "es" ? "Seleccionar" : "Choose")}</span>
            <input type="file" accept=".pdf,.docx,.txt,.md" disabled={busy} onChange={(event) => void importFile(event.target.files?.[0], language)} />
          </label>;
        })}
      </div>
      <small className="resume-local-note">⌂ {locale === "es" ? "PDF, DOCX, TXT o MD · máximo 10 MB cada uno · los originales permanecen en este equipo." : "PDF, DOCX, TXT or MD · 10 MB each · originals stay on this computer."}</small>

      {profile.id && (
        <>
          <div className="profile-summary-card">
            <div><small>{t("profile.name")}</small><strong>{profile.name}</strong></div>
            <div><small>{t("profile.extractedFacts")}</small><strong>{profile.facts.length}</strong></div>
            <div><small>{locale === "es" ? "Revisados" : "Reviewed"}</small><strong>{profile.facts.filter((fact) => fact.verified).length}/{profile.facts.length}</strong></div>
            <div className="profile-readiness"><span>{profile.completion}%</span><div><small>{t("profile.status")}</small><strong>{profile.confirmed ? t("profile.ready") : t("profile.review")}</strong></div></div>
          </div>
          <div className="fact-groups">
            {grouped.map((group) => (
              <section key={group.category}>
                <header><span>{labels[group.category]}</span><b>{group.facts.length}</b></header>
                <div className="fact-review-list">
                  {group.facts.map((fact) => (
                    <article key={fact.id}>
                      <div className="fact-status" aria-label={fact.verified ? "Verificado" : "Pendiente"}>{fact.verified ? "✓" : "•"}</div>
                      <div>
                        {editing === fact.id ? (
                          <div className="fact-edit">
                            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} />
                            <div><button type="button" onClick={async () => { await onUpdateFact(fact, draft); setEditing(null); }}>{t("common.save")}</button><button type="button" className="text-button" onClick={() => setEditing(null)}>{t("common.cancel")}</button></div>
                          </div>
                        ) : (
                          <><p>{fact.text}</p><span className={`fact-language ${fact.language ?? "legacy"}`}>{fact.language?.toUpperCase() ?? (locale === "es" ? "CV anterior" : "Previous résumé")}</span>{(fact.sourcePage || (fact.sourceSpan && fact.sourceSpan.trim() !== fact.text.trim())) && <small className="fact-source">{fact.sourcePage ? `${locale === "es" ? "Página" : "Page"} ${fact.sourcePage}` : locale === "es" ? "Fragmento de origen" : "Source excerpt"}{fact.sourceSpan && fact.sourceSpan.trim() !== fact.text.trim() ? ` · ${fact.sourceSpan}` : ""}</small>}</>
                        )}
                      </div>
                      {editing !== fact.id && <button type="button" className="edit-fact" onClick={() => { setEditing(fact.id); setDraft(fact.text); }} aria-label={`${t("common.edit")}: ${fact.text}`}>✎</button>}
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
          <div className="profile-actions">
            {!profile.confirmed && <button type="button" className="primary-action" disabled={busy || profile.facts.length === 0 || !hasBothResumes} onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}>{busy ? t("profile.confirming") : t("profile.confirm")}</button>}
            {!hasBothResumes && <span className="profile-requirement">{locale === "es" ? "Importa ambos CV para poder confirmar el perfil." : "Upload both résumés to confirm the profile."}</span>}
          </div>
        </>
      )}
    </section>
  );
}

export function SearchView({ profileReady, deepSeekReady, theirStackReady = false, t, locale, onStart, onManualImport }: {
  profileReady: boolean;
  deepSeekReady: boolean;
  theirStackReady?: boolean;
  t: Translate;
  locale: "es" | "en";
  onStart: (role: string) => Promise<void>;
  onManualImport: (input: ManualJobInput) => Promise<void>;
}) {
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manual, setManual] = useState<ManualJobInput>({ title: "", company: "", description: "", location: "Costa Rica", remote: false, source: "linkedin", url: "", posted_at: "" });
  const portals = [
    ["LinkedIn", `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(role)}&location=Costa%20Rica`],
    ["Indeed", `https://cr.indeed.com/jobs?q=${encodeURIComponent(role)}`],
    ["Glassdoor", `https://www.glassdoor.com/Job/jobs.htm?sc.keyword=${encodeURIComponent(role)}`],
    ["Computrabajo", `https://cr.computrabajo.com/trabajo-de-${encodeURIComponent(role.toLowerCase().replace(/\s+/g, "-"))}`],
  ];
  return (
    <section className="view-section career-search">
      <div className="view-heading"><div><span className="eyebrow">02 · {locale === "es" ? "Explorar oportunidades" : "Explore opportunities"}</span><h2>{t("search.title")}</h2><p>{locale === "es" ? "Escribe un rol. Ame ampliará los términos y buscará vacantes recientes en Costa Rica." : "Enter a role. Ame will expand the terms and search recent Costa Rica openings."}</p></div></div>
      <div className="source-hero"><div className="source-mark">TS</div><div><strong>{theirStackReady ? (locale === "es" ? "TheirStack está conectado" : "TheirStack is connected") : (locale === "es" ? "Búsqueda con fuentes de respaldo" : "Fallback source search")}</strong><p>{theirStackReady ? (locale === "es" ? "La primera tanda recupera hasta 25 vacantes de Costa Rica." : "The first batch retrieves up to 25 Costa Rica jobs.") : (locale === "es" ? "Configura TheirStack para incluir LinkedIn, Indeed, Glassdoor, Computrabajo y miles de sitios." : "Configure TheirStack to include LinkedIn, Indeed, Glassdoor, Computrabajo, and thousands of sites.")}</p></div><span className={theirStackReady ? "connected" : "limited"}>{theirStackReady ? "✓" : "!"}</span></div>
      <div className="scope-pills"><span>🇨🇷 Costa Rica</span><span>🗓️ {locale === "es" ? "Últimos 30 días" : "Last 30 days"}</span><span>25 · {locale === "es" ? "por tanda" : "per batch"}</span></div>
      <form className="role-search-form" onSubmit={async (event) => { event.preventDefault(); if (!role.trim() || !profileReady || !deepSeekReady) return; setBusy(true); try { await onStart(role.trim()); } finally { setBusy(false); } }}>
        <label htmlFor="role-query">{t("search.roleLabel")}</label>
        <div className="search-console"><span className="console-prefix" aria-hidden="true">AME://</span><input id="role-query" value={role} onChange={(event) => setRole(event.target.value)} placeholder={t("search.rolePlaceholder")} autoFocus /><button type="submit" disabled={busy || !profileReady || !deepSeekReady || role.trim().length < 2}>{busy ? t("search.searching") : t("search.start")}</button></div>
        <small>{t("search.aliasHint")}</small>
      </form>
      {!profileReady && <div className="inline-warning">{t("search.profileRequired")}</div>}
      {!deepSeekReady && <div className="inline-warning">{locale === "es" ? "Configura tu API key de DeepSeek antes de buscar." : "Configure your DeepSeek API key before searching."}</div>}
      <details className="portal-searches">
        <summary>{locale === "es" ? "Búsqueda manual e importación" : "Manual search and import"}</summary>
        <p>{locale === "es" ? "Abre los portales directamente o importa una publicación que hayas encontrado." : "Open job portals directly or import a posting you found."}</p>
        <div>{portals.map(([label, href]) => <a key={label} href={href} target="_blank" rel="noreferrer">↗ {label}</a>)}</div>
        <button type="button" className="secondary-button" onClick={() => setManualOpen((value) => !value)}>{manualOpen ? (locale === "es" ? "Cerrar importador" : "Close importer") : (locale === "es" ? "Importar una vacante" : "Import a job")}</button>
      </details>
      {manualOpen && <form className="manual-import" onSubmit={async (event) => { event.preventDefault(); setBusy(true); try { await onManualImport({ ...manual, posted_at: manual.posted_at ? new Date(manual.posted_at).toISOString() : undefined }); setManualOpen(false); } finally { setBusy(false); } }}>
        <select value={manual.source} onChange={(event) => setManual({ ...manual, source: event.target.value as ManualJobInput["source"] })}><option value="linkedin">LinkedIn</option><option value="indeed">Indeed</option><option value="glassdoor">Glassdoor</option><option value="computrabajo">Computrabajo</option><option value="manual">{locale === "es" ? "Página oficial" : "Official page"}</option></select>
        <input required placeholder={locale === "es" ? "Nombre del puesto" : "Job title"} value={manual.title} onChange={(event) => setManual({ ...manual, title: event.target.value })} />
        <input required placeholder={locale === "es" ? "Empresa" : "Company"} value={manual.company} onChange={(event) => setManual({ ...manual, company: event.target.value })} />
        <input required type="url" placeholder="https://..." value={manual.url} onChange={(event) => setManual({ ...manual, url: event.target.value })} />
        <label>{locale === "es" ? "Fecha y hora publicadas" : "Publication date and time"}<input required type="datetime-local" value={manual.posted_at} onChange={(event) => setManual({ ...manual, posted_at: event.target.value })} /></label>
        <input placeholder={locale === "es" ? "Ubicación" : "Location"} value={manual.location} onChange={(event) => setManual({ ...manual, location: event.target.value })} />
        <label className="manual-remote"><input type="checkbox" checked={manual.remote} onChange={(event) => setManual({ ...manual, remote: event.target.checked })} />{locale === "es" ? "Es remoto" : "Remote role"}</label>
        <textarea required minLength={40} placeholder={locale === "es" ? "Pega aquí la descripción completa" : "Paste the full description here"} value={manual.description} onChange={(event) => setManual({ ...manual, description: event.target.value })} />
        <button type="submit" disabled={busy}>{locale === "es" ? "Guardar vacante" : "Save job"}</button>
      </form>}
      <p className="search-trust-note">{t("search.trustNote")}</p>
    </section>
  );
}

export function AnalysisPanel({ analysis, t }: { analysis: DeepFitAnalysis; t: Translate }) {
  return <div className="deep-analysis"><header className="analysis-overview"><div className="analysis-score"><strong>{Math.round(analysis.score)}%</strong><span>{t(`results.level.${analysis.level}`)}</span></div><div><small>{t("analysis.resumeUsed")}</small><strong>{analysis.resume_language === "es" ? t("analysis.spanishResume") : t("analysis.englishResume")}</strong><p>{t("analysis.confirmedOnly")}</p></div></header><section><h4>{t("analysis.matches")}</h4>{analysis.matched_requirements.length ? analysis.matched_requirements.map((item) => <div className="match-row" key={`${item.fact_id}-${item.requirement}`}><strong>{item.requirement}</strong><p>{item.evidence}</p></div>) : <p>{t("analysis.noMatches")}</p>}</section>{analysis.missing_requirements.length > 0 && <section className="analysis-gaps"><h4>{t("analysis.missing")}</h4><ul>{analysis.missing_requirements.map((item, index) => <li key={`missing-${index}-${item}`}>{item}</li>)}</ul></section>}<section><h4>{t("analysis.recommendations")}</h4><ul>{analysis.cv_recommendations.map((item, index) => <li key={`recommendation-${index}-${item}`}>{item}</li>)}</ul></section><div className="analysis-caution">{analysis.cautions.join(" ")}</div></div>;
}

function FilterControl({ icon, label, children }: { icon: string; label: string; children: React.ReactNode }) {
  return <div className="filter-control"><span className="filter-control-icon" aria-hidden="true">{icon}</span><label><small>{label}</small>{children}</label><span className="filter-chevron" aria-hidden="true">⌄</span></div>;
}

export function ResultsView({ jobs, analyses, busyJob, aliases, coverageIncomplete, referenceTime, t, locale, onAnalysis, onInterest, canLoadMore = false, loadingMore = false, totalAvailable = null, onLoadMore }: {
  jobs: JobRecord[];
  analyses: Record<string, DeepFitAnalysis>;
  busyJob: string | null;
  aliases: string[];
  coverageIncomplete: boolean;
  referenceTime?: string;
  t: Translate;
  locale: "es" | "en";
  onAnalysis: (job: JobRecord) => Promise<void>;
  onInterest: (job: JobRecord) => Promise<void>;
  canLoadMore?: boolean;
  loadingMore?: boolean;
  totalAvailable?: number | null;
  onLoadMore?: () => Promise<void>;
}) {
  const [period, setPeriod] = useState<"24h" | "7d" | "30d">("30d");
  const [mode, setMode] = useState<"all" | JobRecord["workMode"]>("all");
  const [source, setSource] = useState("all");
  const [fit, setFit] = useState<"all" | JobRecord["fitLevel"]>("all");
  const [visible, setVisible] = useState(24);
  const anchor = referenceTime ? Date.parse(referenceTime) : Date.now();
  const sources = useMemo(() => [...new Set(jobs.map((job) => job.sourcePortal || job.source))].sort(), [jobs]);
  const counts = useMemo(() => ({ "24h": jobs.filter((job) => anchor - Date.parse(job.publishedAt) <= 86_400_000).length, "7d": jobs.filter((job) => anchor - Date.parse(job.publishedAt) <= 604_800_000).length, "30d": jobs.length }), [anchor, jobs]);
  const filtered = useMemo(() => {
    const milliseconds = period === "24h" ? 86_400_000 : period === "7d" ? 604_800_000 : 2_592_000_000;
    return jobs.filter((job) => anchor - Date.parse(job.publishedAt) <= milliseconds && (mode === "all" || job.workMode === mode) && (source === "all" || (job.sourcePortal || job.source) === source) && (fit === "all" || job.fitLevel === fit));
  }, [anchor, fit, jobs, mode, period, source]);

  if (!jobs.length) return <section className="empty-results"><span>30d</span><h2>{t("results.emptyTitle")}</h2><p>{locale === "es" ? "No encontramos publicaciones verificables de los últimos 30 días para este rol." : "No verifiable postings from the last 30 days were found for this role."}</p>{coverageIncomplete && <div className="inline-warning">{t("results.partialCoverage")}</div>}</section>;
  return (
    <section className="view-section career-results">
      <div className="view-heading"><div><span className="eyebrow">03 · {filtered.length} {t("results.verified")}</span><h2>{t("results.title")}</h2><p>{locale === "es" ? `${jobs.length}${totalAvailable ? ` de ${totalAvailable}` : ""} vacantes recuperadas. Los filtros no consumen créditos.` : `${jobs.length}${totalAvailable ? ` of ${totalAvailable}` : ""} jobs retrieved. Filters use no credits.`}</p></div></div>
      <div className="result-filterbar"><div className="period-tabs">{(["24h", "7d", "30d"] as const).map((value) => <button type="button" className={period === value ? "active" : ""} key={value} onClick={() => { setPeriod(value); setVisible(24); }}>{value === "7d" ? (locale === "es" ? "7 días" : "7 days") : value === "30d" ? (locale === "es" ? "30 días" : "30 days") : "24 h"}<b>{counts[value]}</b></button>)}</div><div className="filter-control-row"><FilterControl icon="⌂" label={locale === "es" ? "MODALIDAD" : "WORK MODE"}><select aria-label={locale === "es" ? "Modalidad" : "Work mode"} value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}><option value="all">{locale === "es" ? "Toda modalidad" : "All work modes"}</option><option value="remote">{locale === "es" ? "Remoto" : "Remote"}</option><option value="hybrid">{locale === "es" ? "Híbrido" : "Hybrid"}</option><option value="onsite">{locale === "es" ? "Presencial" : "On-site"}</option></select></FilterControl><FilterControl icon="⌁" label={locale === "es" ? "FUENTE" : "SOURCE"}><select aria-label={locale === "es" ? "Fuente" : "Source"} value={source} onChange={(event) => setSource(event.target.value)}><option value="all">{locale === "es" ? "Todas las fuentes" : "All sources"}</option>{sources.map((value) => <option key={value} value={value}>{value}</option>)}</select></FilterControl><FilterControl icon="◎" label={locale === "es" ? "ENCAJE" : "FIT"}><select aria-label={locale === "es" ? "Encaje" : "Fit"} value={fit} onChange={(event) => setFit(event.target.value as typeof fit)}><option value="all">{locale === "es" ? "Todo encaje" : "All fit levels"}</option><option value="high">{t("results.level.high")}</option><option value="medium">{t("results.level.medium")}</option><option value="low">{t("results.level.low")}</option></select></FilterControl></div></div>
      {aliases.length > 1 && <div className="alias-strip"><strong>{t("results.expandedAs")}</strong>{aliases.map((alias) => <span key={alias}>{alias}</span>)}</div>}
      {coverageIncomplete && <div className="inline-warning">{t("results.partialCoverage")}</div>}
      {!filtered.length ? <div className="filter-empty">{locale === "es" ? "No hay vacantes que coincidan con estos filtros." : "No jobs match these filters."}</div> : <div className="job-grid">{filtered.slice(0, visible).map((job) => <article className="job-result-card" key={job.id}><header><div><span>{job.company}</span><h3>{job.title}</h3><small className={`verification-chip ${job.applyUrlType === "portal" ? "portal" : job.verificationLevel}`}>{job.applyUrlType === "portal" ? `${locale === "es" ? "Enlace de portal" : "Portal link"}${job.sourcePortal ? ` · ${job.sourcePortal}` : ""}` : (locale === "es" ? "Enlace de la empresa" : "Company link")}</small></div><div className={`fit-badge fit-${job.fitLevel}`}><strong>{Math.round(job.fitScore)}%</strong><span>{t(`results.level.${job.fitLevel}`)}</span></div></header><div className="job-meta"><span>📍 {job.location}</span><span>🕘 {formatDate(job.publishedAt, locale)}</span><span>✓ {job.sourcePortal || job.source}</span>{job.provider === "theirstack" && <span>via TheirStack</span>}</div><p className="job-description">{job.description}</p>{!!job.requirements.length && <div className="requirements"><strong>{t("results.requirements")}</strong><ul>{job.requirements.slice(0, 4).map((item, index) => <li key={`${job.id}-requirement-${index}`}>{item}</li>)}</ul></div>}<div className="quick-fit"><div><strong>{t("results.strengths")}</strong><p>{job.evidence.join(" · ") || t("results.noEvidence")}</p></div><div><strong>{t("results.gaps")}</strong><p>{job.gaps.join(" · ") || t("results.noClearGaps")}</p></div></div>{analyses[job.id] && <AnalysisPanel analysis={analyses[job.id]} t={t} />}<footer><button type="button" className="secondary-button" disabled={busyJob === job.id} onClick={() => onAnalysis(job)}>{analyses[job.id] ? t("analysis.loaded") : t("results.analysis")}</button><a className="secondary-button apply-link" href={job.officialApplyUrl} target="_blank" rel="noreferrer">{job.applyUrlType === "company" ? t("results.apply") : (locale === "es" ? "Abrir publicación" : "Open posting")}</a><button type="button" className="interest-button" disabled={busyJob === job.id} onClick={() => onInterest(job)}>♥ {busyJob === job.id ? t("results.preparing") : t("results.interested")}</button></footer></article>)}</div>}
      {visible < filtered.length && <button type="button" className="load-more" onClick={() => setVisible((value) => value + 24)}>{locale === "es" ? `Mostrar más (${filtered.length - visible})` : `Show more (${filtered.length - visible})`}</button>}
      {canLoadMore && onLoadMore && <div className="provider-load-more"><div><strong>{locale === "es" ? "Hay más oportunidades en TheirStack" : "More opportunities are available in TheirStack"}</strong><span>{locale === "es" ? "La siguiente tanda puede consumir hasta 25 créditos." : "The next batch may consume up to 25 credits."}</span></div><button type="button" disabled={loadingMore} onClick={() => void onLoadMore()}>{loadingMore ? (locale === "es" ? "Recuperando…" : "Retrieving…") : (locale === "es" ? "Cargar 25 más" : "Load 25 more")}</button></div>}
    </section>
  );
}

export function InterestsView({ interests, jobs, t, locale, onDownload, onRemove }: { interests: Interest[]; jobs: JobRecord[]; t: Translate; locale: "es" | "en"; onDownload: (interest: Interest) => void; onRemove: (interest: Interest) => Promise<void> }) {
  const jobsById = useMemo(() => Object.fromEntries(jobs.map((job) => [job.id, job])), [jobs]);
  if (!interests.length) return <section className="empty-results"><span>♥</span><h2>{t("interests.emptyTitle")}</h2><p>{t("interests.emptyBody")}</p></section>;
  return <section className="view-section interest-list"><div className="view-heading"><div><span className="eyebrow">04 · {t("interests.saved")}</span><h2>{t("interests.title")}</h2><p>{t("interests.subtitle")}</p></div></div>{interests.map((interest) => { const job = jobsById[interest.job_id]; const ready = interest.guide_status === "ready" && Boolean(interest.guide_artifact_id); return <article key={interest.interest_id}><div><small>{job?.company ?? interest.company}</small><h3>{job?.title ?? interest.job_title}</h3><span>{formatDate(interest.created_at, locale)} · PDF {interest.guide_language.toUpperCase()}</span><span className={`guide-status ${interest.guide_status}`}>{interest.guide_status === "ready" ? (locale === "es" ? "PDF listo" : "PDF ready") : interest.guide_status === "failed" ? (locale === "es" ? "Error al crear PDF" : "PDF failed") : (locale === "es" ? "Creando PDF…" : "Creating PDF…")}</span>{interest.guide_error && <small className="guide-error">{interest.guide_error}</small>}</div><div><a className="text-button" href={job?.officialApplyUrl ?? interest.official_apply_url} target="_blank" rel="noreferrer">{t("results.apply")}</a><button type="button" className="primary-action" disabled={!ready} onClick={() => onDownload(interest)}>{ready ? t("interests.download") : (locale === "es" ? "Preparando…" : "Preparing…")}</button><button type="button" className="text-button danger" onClick={() => onRemove(interest)}>{t("interests.remove")}</button></div></article>; })}</section>;
}

function ProviderKeyCard({ provider, description, configured, keyValue, setKeyValue, busy, onSave, onDelete, note, statusDetail, locale }: {
  provider: string;
  description: string;
  configured: boolean;
  keyValue: string;
  setKeyValue: (value: string) => void;
  busy: boolean;
  onSave: () => Promise<void>;
  onDelete: () => Promise<void>;
  note: string;
  statusDetail?: string;
  locale: "es" | "en";
}) {
  const saveLabel = configured
    ? (locale === "es" ? "Actualizar" : "Update")
    : (locale === "es" ? "Validar y guardar" : "Validate and save");
  return <article className={`provider-card ${configured ? "is-connected" : ""}`}><div className="provider-circuit" aria-hidden="true"><i /><i /><i /><i /></div><header><div className="provider-logo">{provider.slice(0, 2).toUpperCase()}</div><div><strong>{provider}</strong><p>{description}</p></div><span className={configured ? "configured" : "missing"}><i />{configured ? "ONLINE" : "OFFLINE"}</span></header><form onSubmit={(event) => { event.preventDefault(); void onSave(); }}><label className="api-key-field"><span>API ACCESS KEY</span><input aria-label={`${provider} API key`} type="password" autoComplete="off" value={keyValue} onChange={(event) => setKeyValue(event.target.value)} placeholder="•••• •••• •••• ••••" /></label><button type="submit" disabled={busy || keyValue.trim().length < 8}>{busy ? "…" : saveLabel}</button></form><div className="provider-details"><small>{note}</small>{statusDetail && <span className="credit-balance">{statusDetail}</span>}</div>{configured && <button type="button" className="text-button danger" onClick={() => void onDelete()}>{locale === "es" ? "Eliminar clave guardada" : "Delete saved key"}</button>}</article>;
}

export function SettingsView({ t, locale, deepSeekStatus, theirStackStatus, onSaveDeepSeek, onDeleteDeepSeek, onSaveTheirStack, onDeleteTheirStack }: {
  t: Translate;
  locale: "es" | "en";
  deepSeekStatus: DeepSeekStatus | null;
  theirStackStatus: TheirStackStatus | null;
  onSaveDeepSeek: (key: string) => Promise<void>;
  onDeleteDeepSeek: () => Promise<void>;
  onSaveTheirStack: (key: string) => Promise<void>;
  onDeleteTheirStack: () => Promise<void>;
}) {
  const [deepSeekKey, setDeepSeekKey] = useState("");
  const [theirStackKey, setTheirStackKey] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const perform = async (provider: string, action: () => Promise<void>) => { setBusy(provider); setError(""); try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(null); } };
  const creditStatus = theirStackStatus?.configured
    ? theirStackStatus.api_credits != null
      ? (locale === "es" ? `${theirStackStatus.api_credits} créditos API disponibles` : `${theirStackStatus.api_credits} API credits available`)
      : (locale === "es" ? "Conexión validada" : "Connection validated")
    : undefined;
  return <section className="view-section settings-view"><div className="view-heading"><div><span className="eyebrow">{locale === "es" ? "Conexiones y privacidad" : "Connections and privacy"}</span><h2>{t("settings.title")}</h2><p>{locale === "es" ? "Las claves se validan y guardan exclusivamente en el Administrador de credenciales de Windows." : "Keys are validated and stored exclusively in Windows Credential Manager."}</p></div></div>{error && <div className="inline-warning">{error}</div>}<div className="provider-grid"><ProviderKeyCard provider="TheirStack" locale={locale} description={locale === "es" ? "Búsqueda de vacantes en Costa Rica" : "Costa Rica job search"} configured={Boolean(theirStackStatus?.configured)} keyValue={theirStackKey} setKeyValue={setTheirStackKey} busy={busy === "theirstack"} onSave={() => perform("theirstack", async () => { await onSaveTheirStack(theirStackKey); setTheirStackKey(""); })} onDelete={() => perform("theirstack", onDeleteTheirStack)} note={locale === "es" ? "25 vacantes por tanda. Cada vacante devuelta puede consumir 1 crédito." : "25 jobs per batch. Each returned job may consume 1 credit."} statusDetail={creditStatus} /><ProviderKeyCard provider="DeepSeek" locale={locale} description={locale === "es" ? "Análisis del CV y guías de entrevista" : "Résumé analysis and interview guides"} configured={Boolean(deepSeekStatus?.configured)} keyValue={deepSeekKey} setKeyValue={setDeepSeekKey} busy={busy === "deepseek"} onSave={() => perform("deepseek", async () => { await onSaveDeepSeek(deepSeekKey); setDeepSeekKey(""); })} onDelete={() => perform("deepseek", onDeleteDeepSeek)} note={locale === "es" ? "Sólo recibe hechos profesionales confirmados, nunca tu PDF ni datos de contacto." : "Receives only confirmed professional facts, never your PDF or contact details."} statusDetail={deepSeekStatus?.configured ? (locale === "es" ? "Conexión validada" : "Connection validated") : undefined} /></div><div className="settings-cards"><article><span>⌂</span><div><strong>{t("settings.cvTitle")}</strong><p>{locale === "es" ? "El CV original, la base de datos y las guías permanecen en este equipo." : "The original résumé, database, and guides remain on this computer."}</p></div></article><article><span>↗</span><div><strong>{t("settings.applicationsTitle")}</strong><p>{t("settings.applications")}</p></div></article></div></section>;
}
