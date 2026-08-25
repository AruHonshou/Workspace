import { lazy, Suspense, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { api, type BackendCareerResult, type BackendProfile, type ManualJobInput } from "./api/client";
import { InterestsView, ProfileView, ResultsView, SearchView, SettingsView } from "./components/DashboardViews";
import { WorkspaceModal } from "./components/WorkspaceModal";
import { useGraphRuntime } from "./hooks/useGraphRuntime";
import { useReducedMotion } from "./hooks/useReducedMotion";
import { createTranslator } from "./i18n";
import type { CandidateProfile, DeepFitAnalysis, DeepSeekStatus, Interest, JobRecord, Locale, ProfileFact, TheirStackStatus, ViewId } from "./types";

type PanelId = ViewId;

const OrchestratorScene = lazy(() => import("./components/OrchestratorScene").then((module) => ({ default: module.OrchestratorScene })));

const EMPTY_PROFILE: CandidateProfile = {
  id: null,
  name: "",
  headline: "",
  location: "Costa Rica",
  targetRoles: [],
  completion: 0,
  confirmed: false,
  facts: [],
  resumes: {},
};

const CONTROLS: Array<{ id: PanelId; icon: string }> = [
  { id: "profile", icon: "user" },
  { id: "search", icon: "search" },
  { id: "results", icon: "briefcase" },
  { id: "interests", icon: "heart" },
];

function ControlIcon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    user: <><circle cx="12" cy="8" r="3.2" /><path d="M5.8 20c.6-4 2.6-6 6.2-6s5.6 2 6.2 6" /></>,
    search: <><circle cx="10.5" cy="10.5" r="5.7" /><path d="m15 15 4.2 4.2" /></>,
    briefcase: <><rect x="3.5" y="7" width="17" height="12" rx="2" /><path d="M8.5 7V5.2h7V7M3.5 12h17" /></>,
    heart: <path d="M12 20s-8-4.7-8-10a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.3-8 10-8 10Z" />,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function mapProfile(value: BackendProfile): CandidateProfile {
  const facts: ProfileFact[] = value.facts.map((fact) => ({
    id: fact.fact_id,
    category: (["experience", "skill", "education", "achievement", "preference"] as const).includes(fact.category as ProfileFact["category"])
      ? fact.category as ProfileFact["category"] : "experience",
    text: fact.text,
    verified: fact.verified,
    evidence: fact.evidence,
    sourcePage: fact.source_page,
    sourceSpan: fact.source_span,
    language: fact.language,
  }));
  const resumes = Object.fromEntries(
    Object.entries(value.resumes ?? {}).map(([language, resume]) => [
      language,
      {
        language: language as "es" | "en",
        filename: resume.filename,
        importedAt: resume.imported_at,
        factCount: facts.filter((fact) => fact.language === language).length,
      },
    ]),
  ) as CandidateProfile["resumes"];
  const resumeCount = Object.keys(resumes).length;
  const bilingualConfirmed = value.confirmed && resumeCount === 2;
  return {
    id: value.profile_id,
    name: value.name,
    headline: value.summary,
    location: value.preferences?.desired_locations?.join(", ") || "Costa Rica",
    targetRoles: value.preferences?.desired_titles ?? [],
    completion: bilingualConfirmed ? 100 : resumeCount === 2 ? 75 : resumeCount === 1 ? 35 : facts.length ? 20 : 0,
    confirmed: bilingualConfirmed,
    facts,
    resumes,
  };
}

function mapCareerResult(value: BackendCareerResult): JobRecord {
  return {
    id: value.job_id,
    company: value.company,
    title: value.title,
    location: value.location,
    workMode: /\b(hybrid|híbrido|hibrido)\b/i.test(value.location)
      ? "hybrid"
      : value.remote === true || /\b(remote|remoto)\b/i.test(value.location)
        ? "remote"
        : "onsite",
    source: value.source,
    sources: value.sources ?? [value.source],
    verificationLevel: value.verification_level ?? "official",
    publishedAt: value.published_at,
    officialApplyUrl: value.apply_url ?? value.official_apply_url,
    applyUrlType: value.apply_url_type ?? "company",
    provider: value.provider,
    sourcePortal: value.source_portal,
    sourceUrl: value.source_url,
    description: value.description_summary,
    requirements: value.requirements,
    fitScore: value.fit_summary.score,
    fitLevel: value.fit_summary.level,
    evidence: value.fit_summary.strengths,
    gaps: value.fit_summary.gaps,
  };
}

export default function App() {
  const reducedMotion = useReducedMotion();
  const [locale, setLocale] = useState<Locale>(() => (localStorage.getItem("career-orbit-locale") as Locale) || "es");
  const [activePanel, setActivePanel] = useState<PanelId | null>(null);
  const [profile, setProfile] = useState<CandidateProfile>(EMPTY_PROFILE);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [interests, setInterests] = useState<Interest[]>([]);
  const [analyses, setAnalyses] = useState<Record<string, DeepFitAnalysis>>({});
  const [aliases, setAliases] = useState<string[]>([]);
  const [coverageIncomplete, setCoverageIncomplete] = useState(false);
  const [searchReferenceTime, setSearchReferenceTime] = useState<string | undefined>();
  const [deepSeekStatus, setDeepSeekStatus] = useState<DeepSeekStatus | null>(null);
  const [theirStackStatus, setTheirStackStatus] = useState<TheirStackStatus | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [canLoadMore, setCanLoadMore] = useState(false);
  const [totalAvailable, setTotalAvailable] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busyJob, setBusyJob] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [searchRunId, setSearchRunId] = useState<string | null>(() => localStorage.getItem("career-orchestrator-active-run"));
  const runtime = useGraphRuntime([], reducedMotion);
  const syncedRun = useRef<string | null>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const t = useMemo(() => createTranslator(locale), [locale]);
  const latestEvent = runtime.visibleEvents.at(-1);
  const activityProgress = latestEvent?.ui.progress;
  const activityRunning = busyJob !== null || runtime.state.runState === "running";

  function trackPointerGlow(event: ReactPointerEvent<HTMLDivElement>): void {
    if (reducedMotion || !shellRef.current) return;
    const bounds = shellRef.current.getBoundingClientRect();
    shellRef.current.style.setProperty("--pointer-x", `${event.clientX - bounds.left}px`);
    shellRef.current.style.setProperty("--pointer-y", `${event.clientY - bounds.top}px`);
  }

  useEffect(() => {
    document.documentElement.lang = locale;
    localStorage.setItem("career-orbit-locale", locale);
  }, [locale]);

  useEffect(() => {
    void api.getDeepSeekSettings().then(setDeepSeekStatus).catch(() => setDeepSeekStatus(null));
    void api.getTheirStackSettings().then(setTheirStackStatus).catch(() => setTheirStackStatus(null));
    void api.listProfiles().then(async (profiles) => {
      const preferred = localStorage.getItem("career-orchestrator-profile-id");
      const selected = profiles.find((item) => item.profile_id === preferred) ?? profiles[0];
      if (!selected) { setActivePanel("profile"); return; }
      setProfile(mapProfile(selected));
      localStorage.setItem("career-orchestrator-profile-id", selected.profile_id);
      setInterests(await api.listInterests(selected.profile_id));
    }).catch(() => setActivePanel("profile"));

    const runId = localStorage.getItem("career-orchestrator-active-run");
    if (runId) runtime.connectToRun(runId);
    // Initial restoration happens once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const runId = runtime.activeRunId;
    if (!runId || runId !== searchRunId || runtime.state.runState !== "completed" || syncedRun.current === runId) return;
    syncedRun.current = runId;
    void api.getCareerSearch(runId).then((run) => {
      setJobs((run.result.career_results ?? []).map(mapCareerResult));
      setAliases(run.result.aliases ?? []);
      setCoverageIncomplete(Boolean(run.result.coverage?.sources_failed?.length));
      setSearchReferenceTime(run.result.window_ended_at ?? run.created_at);
      setNextPage(run.result.next_page ?? null);
      setCanLoadMore(Boolean(run.result.can_load_more));
      setTotalAvailable(run.result.total_available ?? null);
      setActivePanel("results");
      setNotice(t("notice.searchComplete", { jobs: run.result.career_results?.length ?? 0 }));
    }).catch((error) => setNotice(error instanceof Error ? error.message : String(error)));
  }, [runtime.activeRunId, runtime.state.runState, searchRunId, t]);

  useEffect(() => {
    if (!latestEvent?.ui?.template_key) return;
    setNotice(t(latestEvent.ui.template_key, latestEvent.ui.template_args));
  }, [latestEvent?.event_id, latestEvent?.ui?.template_args, latestEvent?.ui?.template_key, t]);

  async function importProfile(file: File, language: "es" | "en"): Promise<void> {
    const imported = await api.importProfile(file, language, profile.id);
    const mapped = mapProfile(imported.profile);
    setProfile(mapped);
    setJobs([]);
    setInterests([]);
    localStorage.setItem("career-orchestrator-profile-id", imported.profile.profile_id);
    setNotice(imported.warnings[0] || t("notice.profileImported"));
  }

  async function updateFact(fact: ProfileFact, text: string): Promise<void> {
    const updated = await api.patchProfileFact(fact.id, { text });
    setProfile(mapProfile(updated));
  }

  async function confirmProfile(): Promise<void> {
    if (!profile.id) return;
    const updated = await api.confirmProfile(profile.id);
    setProfile(mapProfile(updated));
    setNotice(t("notice.profileReady"));
  }

  async function startSearch(role: string): Promise<void> {
    if (!profile.id || !profile.confirmed) { setActivePanel("profile"); return; }
    if (!deepSeekStatus?.configured) { setActivePanel("settings"); return; }
    const run = await api.createCareerSearch(profile.id, role);
    if (!run.run_id) throw new Error("Missing search identifier");
    setJobs([]);
    setAnalyses({});
    setAliases([]);
    setNextPage(null);
    setCanLoadMore(false);
    setTotalAvailable(null);
    syncedRun.current = null;
    runtime.connectToRun(run.run_id);
    setSearchRunId(run.run_id);
    localStorage.setItem("career-orchestrator-active-run", run.run_id);
    setActivePanel(null);
  }

  async function importManualJob(input: ManualJobInput): Promise<void> {
    await api.createManualJob(input);
    setNotice(locale === "es" ? "Vacante guardada. Se incluirá cuando busques ese rol." : "Job saved. It will be included when you search for that role.");
  }

  async function saveDeepSeekKey(key: string): Promise<void> {
    const status = await api.saveDeepSeekKey(key);
    setDeepSeekStatus(status);
    setNotice(locale === "es" ? "DeepSeek quedó configurado y listo." : "DeepSeek is configured and ready.");
  }

  async function deleteDeepSeekKey(): Promise<void> {
    const status = await api.deleteDeepSeekKey();
    setDeepSeekStatus(status);
    setNotice(locale === "es" ? "La clave de DeepSeek fue eliminada." : "The DeepSeek key was deleted.");
  }

  async function saveTheirStackKey(key: string): Promise<void> {
    const status = await api.saveTheirStackKey(key);
    setTheirStackStatus(status);
    setNotice(locale === "es" ? "TheirStack quedó configurado y listo." : "TheirStack is configured and ready.");
  }

  async function deleteTheirStackKey(): Promise<void> {
    const status = await api.deleteTheirStackKey();
    setTheirStackStatus(status);
    setNotice(locale === "es" ? "La clave de TheirStack fue eliminada." : "The TheirStack key was deleted.");
  }

  async function loadMoreResults(): Promise<void> {
    if (!searchRunId || nextPage == null || loadingMore) return;
    setLoadingMore(true);
    try {
      const run = await api.loadMoreCareerResults(searchRunId, nextPage);
      setJobs((run.result.career_results ?? []).map(mapCareerResult));
      setNextPage(run.result.next_page ?? null);
      setCanLoadMore(Boolean(run.result.can_load_more));
      setTotalAvailable(run.result.total_available ?? null);
      setCoverageIncomplete(Boolean(run.result.coverage?.sources_failed?.length));
    } finally {
      setLoadingMore(false);
    }
  }

  async function analyze(job: JobRecord): Promise<void> {
    if (!profile.id || analyses[job.id]) return;
    setBusyJob(job.id);
    try {
      setNotice(locale === "es" ? "Comparando los requisitos con el CV correspondiente…" : "Comparing requirements with the matching résumé…");
      const analysis = await api.getJobAnalysis(job.id, profile.id);
      setAnalyses((current) => ({ ...current, [job.id]: analysis }));
      setNotice(locale === "es" ? `Análisis terminado con el CV en ${analysis.resume_language === "es" ? "español" : "inglés"}.` : `Analysis completed with the ${analysis.resume_language === "es" ? "Spanish" : "English"} résumé.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
    finally { setBusyJob(null); }
  }

  async function markInterest(job: JobRecord): Promise<void> {
    if (!profile.id || !searchRunId) return;
    setBusyJob(job.id);
    setNotice(t("notice.guidePreparing"));
    try {
      let interest = await api.createInterest(job.id, profile.id, searchRunId);
      const saveInterest = (value: Interest) => setInterests((current) => [value, ...current.filter((item) => item.interest_id !== value.interest_id)]);
      saveInterest(interest);
      setAnalyses((current) => ({ ...current, [job.id]: interest.analysis }));
      if (interest.guide_run_id) runtime.connectToRun(interest.guide_run_id);
      for (let attempt = 0; interest.guide_status === "preparing" && attempt < 240; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        interest = await api.getInterest(interest.interest_id);
        saveInterest(interest);
      }
      if (interest.guide_status === "failed") {
        throw new Error(interest.guide_error || (locale === "es" ? "No se pudo crear el PDF. Inténtalo de nuevo." : "The PDF could not be created. Try again."));
      }
      if (interest.guide_status !== "ready" || !interest.guide_artifact_id) {
        throw new Error(locale === "es" ? "La creación del PDF tardó demasiado. Puedes reintentar." : "PDF creation timed out. You can retry.");
      }
      setNotice(t("notice.guideReady"));
      setActivePanel("interests");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally { setBusyJob(null); }
  }

  function downloadGuide(interest: Interest): void {
    window.location.assign(api.interviewGuideUrl(interest.interest_id));
  }

  async function removeInterest(interest: Interest): Promise<void> {
    await api.deleteInterest(interest.interest_id);
    setInterests((current) => current.filter((item) => item.interest_id !== interest.interest_id));
  }

  function panelContent(panel: PanelId) {
    if (panel === "profile") return <ProfileView profile={profile} t={t} locale={locale} onImport={importProfile} onUpdateFact={updateFact} onConfirm={confirmProfile} />;
    if (panel === "search") return <SearchView profileReady={profile.confirmed} deepSeekReady={Boolean(deepSeekStatus?.configured)} theirStackReady={Boolean(theirStackStatus?.configured)} t={t} locale={locale} onStart={startSearch} onManualImport={importManualJob} />;
    if (panel === "results") return <ResultsView jobs={jobs} analyses={analyses} busyJob={busyJob} aliases={aliases} coverageIncomplete={coverageIncomplete} referenceTime={searchReferenceTime} t={t} locale={locale} onAnalysis={analyze} onInterest={markInterest} canLoadMore={canLoadMore} loadingMore={loadingMore} totalAvailable={totalAvailable} onLoadMore={loadMoreResults} />;
    if (panel === "interests") return <InterestsView interests={interests} jobs={jobs} t={t} locale={locale} onDownload={downloadGuide} onRemove={removeInterest} />;
    return <SettingsView t={t} locale={locale} deepSeekStatus={deepSeekStatus} theirStackStatus={theirStackStatus} onSaveDeepSeek={saveDeepSeekKey} onDeleteDeepSeek={deleteDeepSeekKey} onSaveTheirStack={saveTheirStackKey} onDeleteTheirStack={deleteTheirStackKey} />;
  }

  const panelTitles: Record<PanelId, string> = {
    profile: t("nav.profile"),
    search: t("nav.search"),
    results: t("nav.results"),
    interests: t("nav.interests"),
    settings: t("nav.settings"),
  };
  return <div className="experience-shell" ref={shellRef} onPointerMove={trackPointerGlow}>
    <a className="skip-link" href="#control-dock">{t("app.skip")}</a>
    <Suspense fallback={<div className="terrarium-fallback" role="img" aria-label={locale === "es" ? "Ame en su terrario retro" : "Ame in her retro terrarium"}><img src="/models/ame-terrarium-poster.svg" alt="" /></div>}><OrchestratorScene reducedMotion={reducedMotion} locale={locale} /></Suspense>
    <header className="experience-header"><div className="mini-brand"><span>AO</span><div><strong>Ame Orbit</strong><small>{locale === "es" ? "Tu estudio de carrera" : "Your career studio"}</small></div></div><div className="runtime-badges"><span className="origin-badge">🇨🇷 {locale === "es" ? "30 días" : "30 days"}</span><span className={`origin-badge ${theirStackStatus?.configured ? "ai-ready" : "ai-missing"}`}>TheirStack {theirStackStatus?.configured ? `✓${theirStackStatus.api_credits != null ? ` · ${theirStackStatus.api_credits}` : ""}` : locale === "es" ? "respaldo" : "fallback"}</span></div><div className="header-actions"><button type="button" className="settings-button" onClick={() => setActivePanel("settings")} aria-label={t("nav.settings")}><ControlIcon name="settings" /></button><button className="language-button" type="button" onClick={() => { setLocale(locale === "es" ? "en" : "es"); setNotice(null); }}>{locale === "es" ? "EN" : "ES"}</button></div></header>
    <div className="welcome-copy"><span>{locale === "es" ? "ORQUESTADORA PERSONAL" : "PERSONAL ORCHESTRATOR"}</span><h1>{locale === "es" ? "Tu próxima oportunidad empieza aquí." : "Your next opportunity starts here."}</h1><p>{locale === "es" ? "Prepara tu CV, descubre empleos en Costa Rica y llega a cada entrevista con un plan." : "Prepare your résumé, discover Costa Rica jobs, and arrive at every interview with a plan."}</p></div>
    {notice && <div className={`notice ${activityRunning ? "is-working" : ""}`} role="status"><span className="notice-signal" aria-hidden="true">{activityRunning ? "◎" : "✓"}</span><span className="notice-copy"><strong>{activityRunning ? (locale === "es" ? "PROCESANDO" : "PROCESSING") : (locale === "es" ? "ACTUALIZACIÓN" : "UPDATE")}</strong>{notice}</span><span className="notice-dots" aria-hidden="true"><i /><i /><i /></span><button type="button" onClick={() => setNotice(null)}>×</button>{activityRunning && <span className="notice-progress" style={{ width: `${Math.max(8, Math.round((activityProgress ?? .15) * 100))}%` }} />}</div>}
    <nav id="control-dock" className="control-dock" aria-label={t("nav.aria")}>{CONTROLS.map((item) => <button key={item.id} type="button" className={activePanel === item.id ? "active" : ""} onClick={() => setActivePanel(item.id)}><ControlIcon name={item.icon} /><span>{t(`nav.${item.id}`)}</span>{item.id === "results" && jobs.length > 0 && <b>{jobs.length}</b>}{item.id === "interests" && interests.length > 0 && <b>{interests.length}</b>}</button>)}</nav>
    <div className="fan-credit">Fan project · Terrarium by Seafoam · CC BY 4.0 · {locale === "es" ? "No oficial" : "Unofficial"}</div>
    {activePanel && <WorkspaceModal title={panelTitles[activePanel]} eyebrow={t("app.assistant")} wide={activePanel === "results"} onClose={() => setActivePanel(null)} closeLabel={t("common.close")}>{panelContent(activePanel)}</WorkspaceModal>}
  </div>;
}
