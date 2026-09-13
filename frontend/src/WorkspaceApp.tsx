import { useCallback, useEffect, useMemo, useState } from "react";
import { api, applyLinkedInOptimization, DEMO_MODE, type BackendProfile } from "./api/client";
import { DesktopShell } from "./app/DesktopShell";
import { ProfileView, SettingsView } from "./components/DashboardViews";
import { LinkedInView } from "./components/GlobalViews";
import { createTranslator } from "./i18n";
import { SavedJobsPage } from "./pages/SavedJobsPage";
import { AboutMePage } from "./pages/AboutMePage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { SimpleSearchPage } from "./pages/SimpleSearchPage";
import type {
  CandidateProfile,
  CountryOption,
  DeepSeekStatus,
  LinkedInOptimizationVersion,
  LinkedInProfileSnapshot,
  Locale,
  ProfileFact,
  TheirStackStatus,
  ViewId,
} from "./types";
import "./styles/pages.css";

const EMPTY_PROFILE: CandidateProfile = {
  id: null, displayName: "", name: "", headline: "", location: "", targetRoles: [],
  revision: 1, completion: 0, confirmed: false, facts: [], resumes: {},
  preferences: { desiredTitles: [], targetSeniorities: [], allowedWorkModes: [], desiredLocations: [], excludedKeywords: [], excludedSectors: [] },
  redactedPreview: null, cloudConsent: null, cloudConsentValid: false,
};

function mapProfile(value: BackendProfile): CandidateProfile {
  const facts: ProfileFact[] = value.facts.map((fact) => ({
    id: fact.fact_id,
    category: (["experience", "project", "skill", "education", "certification", "achievement", "preference"] as const).includes(fact.category as ProfileFact["category"]) ? fact.category as ProfileFact["category"] : "experience",
    text: fact.text, verified: fact.verified, evidence: fact.evidence,
    sourcePage: fact.source_page, sourceSpan: fact.source_span, language: fact.language,
  }));
  const resumes = Object.fromEntries(Object.entries(value.resumes ?? {}).map(([language, resume]) => [language, {
    language, filename: resume.filename, importedAt: resume.imported_at,
    factCount: facts.filter((fact) => fact.language === language).length,
  }])) as CandidateProfile["resumes"];
  const ready = value.confirmed && Object.keys(resumes).length > 0;
  const consentValid = Boolean(value.cloud_processing_consent?.status === "granted"
    && value.cloud_processing_consent.profile_revision === value.revision
    && value.redacted_preview?.profile_revision === value.revision
    && value.cloud_processing_consent.preview_id === value.redacted_preview?.preview_id);
  return {
    id: value.profile_id, displayName: value.display_name ?? value.name ?? "Perfil actual",
    name: value.name, headline: value.summary,
    location: value.preferences?.desired_locations?.join(", ") || "",
    targetRoles: value.preferences?.desired_titles ?? [], revision: value.revision ?? 1,
    completion: ready ? 100 : Object.keys(resumes).length ? 70 : facts.length ? 20 : 0,
    confirmed: ready, facts, resumes,
    preferences: {
      desiredTitles: value.preferences?.desired_titles ?? [], desiredLocations: value.preferences?.desired_locations ?? [],
      targetSeniorities: value.preferences?.target_seniorities ?? [], allowedWorkModes: value.preferences?.allowed_work_modes ?? [],
      excludedKeywords: value.preferences?.excluded_keywords ?? [], excludedSectors: value.preferences?.excluded_sectors ?? [],
    },
    redactedPreview: value.redacted_preview ?? null,
    cloudConsent: value.cloud_processing_consent ?? null,
    cloudConsentValid: consentValid,
  };
}

export default function WorkspaceApp() {
  const [locale, setLocale] = useState<Locale>(() => localStorage.getItem("career-orbit-locale") === "en" ? "en" : "es");
  const [notice, setNotice] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<CandidateProfile[]>([]);
  const [profile, setProfile] = useState<CandidateProfile>(EMPTY_PROFILE);
  const [profileLoadError, setProfileLoadError] = useState<string | null>(null);
  const [countries, setCountries] = useState<CountryOption[]>([]);
  const [deepSeekStatus, setDeepSeekStatus] = useState<DeepSeekStatus | null>(null);
  const [theirStackStatus, setTheirStackStatus] = useState<TheirStackStatus | null>(null);
  const [linkedInSnapshot, setLinkedInSnapshot] = useState<LinkedInProfileSnapshot | null>(null);
  const [linkedInVersions, setLinkedInVersions] = useState<LinkedInOptimizationVersion[]>([]);
  const [linkedInBusy, setLinkedInBusy] = useState(false);
  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 4200);
    return () => window.clearTimeout(timeout);
  }, [notice]);
  const t = useMemo(() => createTranslator(locale), [locale]);

  const restoreProfiles = useCallback(async () => {
    try {
      const mapped = (await api.listProfiles()).map(mapProfile);
      setProfiles(mapped);
      const preferred = localStorage.getItem("workspace-profile-id");
      const selected = mapped.find((item) => item.id === preferred) ?? mapped[0] ?? EMPTY_PROFILE;
      setProfile(selected);
      if (selected.id) localStorage.setItem("workspace-profile-id", selected.id);
      setProfileLoadError(null);
    } catch (error) {
      setProfileLoadError(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }, []);

  useEffect(() => { document.documentElement.lang = locale; localStorage.setItem("career-orbit-locale", locale); }, [locale]);
  useEffect(() => {
    let retryTimer: number | undefined;
    const loadProfiles = async () => {
      try { await restoreProfiles(); }
      catch { retryTimer = window.setTimeout(() => { void restoreProfiles().catch(() => undefined); }, 500); }
    };
    void Promise.allSettled([
      loadProfiles(),
      api.listCountries().then(setCountries),
      api.getDeepSeekSettings().then(setDeepSeekStatus),
      api.getTheirStackSettings().then(setTheirStackStatus),
    ]);
    return () => { if (retryTimer !== undefined) window.clearTimeout(retryTimer); };
  }, [restoreProfiles]);
  useEffect(() => {
    let active = true;
    if (!profile.id) { setLinkedInSnapshot(null); setLinkedInVersions([]); return; }
    void api.listLinkedInImports(profile.id).then(async (items) => {
      const latest = items[0] ?? null;
      if (!active) return;
      if (!latest) { setLinkedInSnapshot(null); setLinkedInVersions([]); return; }
      const versions = await api.listLinkedInOptimizations(latest.snapshot_id);
      if (!active) return;
      setLinkedInVersions(versions);
      setLinkedInSnapshot(versions[0] ? applyLinkedInOptimization(latest, versions[0]) : latest);
    }).catch(() => { if (active) { setLinkedInSnapshot(null); setLinkedInVersions([]); } });
    return () => { active = false; };
  }, [profile.id]);

  function storeProfile(value: BackendProfile) {
    const mapped = mapProfile(value);
    setProfiles((current) => [mapped, ...current.filter((item) => item.id !== mapped.id)]);
    setProfile(mapped);
    if (mapped.id) localStorage.setItem("workspace-profile-id", mapped.id);
    return mapped;
  }
  async function selectProfile(id: string) { const selected = profiles.find((item) => item.id === id); if (selected) { setProfile(selected); localStorage.setItem("workspace-profile-id", id); } }
  async function createProfile(name: string) { storeProfile(await api.createProfile(name)); setNotice(locale === "es" ? "Perfil creado." : "Profile created."); }
  async function renameProfile(name: string) { if (profile.id) storeProfile(await api.updateProfile(profile.id, { display_name: name })); }
  async function duplicateProfile() { if (profile.id) storeProfile(await api.duplicateProfile(profile.id)); }
  async function deleteProfile() {
    if (!profile.id) return;
    await api.deleteProfile(profile.id);
    const remaining = profiles.filter((item) => item.id !== profile.id);
    const next = remaining[0] ?? EMPTY_PROFILE;
    setProfiles(remaining); setProfile(next);
    if (next.id) localStorage.setItem("workspace-profile-id", next.id);
    else localStorage.removeItem("workspace-profile-id");
  }
  async function updatePreferences(preferences: CandidateProfile["preferences"]) {
    if (!profile.id) return;
    storeProfile(await api.updateProfile(profile.id, { preferences: {
      desired_titles: preferences.desiredTitles, desired_locations: preferences.desiredLocations,
      target_seniorities: preferences.targetSeniorities, allowed_work_modes: preferences.allowedWorkModes,
      excluded_keywords: preferences.excludedKeywords, excluded_sectors: preferences.excludedSectors,
    } }));
  }
  async function importProfile(file: File, language: string) { const result = await api.importProfile(file, language, profile.id); storeProfile(result.profile); setNotice(result.warnings[0] || t("notice.profileImported")); }
  async function updateFact(fact: ProfileFact, text: string) { storeProfile(await api.patchProfileFact(fact.id, { text })); }
  async function confirmProfile() { if (profile.id) storeProfile(await api.confirmProfile(profile.id)); }
  async function reprocessProfile() { if (profile.id) { storeProfile(await api.reprocessProfile(profile.id)); setNotice(locale === "es" ? "Extracción optimizada. Revisa y confirma nuevamente los hechos profesionales." : "Extraction optimized. Review and confirm the professional facts again."); } }
  async function cloudConsent(granted: boolean) { if (profile.id) storeProfile(await api.decideCloudConsent(profile.id, granted)); }
  function linkedinError(error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    if (/deepseek|linkedin optimization|optimización de linkedin/i.test(message)) {
      return locale === "es"
        ? "DeepSeek no pudo completar la optimización de LinkedIn. Puedes intentarlo nuevamente."
        : "DeepSeek could not complete the LinkedIn optimization. Please try again.";
    }
    return message || (locale === "es" ? "No se pudo completar la operación de LinkedIn." : "The LinkedIn operation could not be completed.");
  }
  async function importLinkedInFile(file: File, language: string) { if (!profile.id) return; setLinkedInBusy(true); try { const value = await api.importLinkedIn(file, profile.id, language); setLinkedInSnapshot(value); setLinkedInVersions([]); } catch (error) { setNotice(linkedinError(error)); } finally { setLinkedInBusy(false); } }
  async function importLinkedInText(text: string, language: string) { if (!profile.id) return; setLinkedInBusy(true); try { const value = await api.importLinkedInText(profile.id, language, text); setLinkedInSnapshot(value); setLinkedInVersions([]); } catch (error) { setNotice(linkedinError(error)); } finally { setLinkedInBusy(false); } }
  async function optimizeLinkedIn(roles: string[], language: string) { if (!linkedInSnapshot) return; setLinkedInBusy(true); try { const value = await api.optimizeLinkedIn(linkedInSnapshot, roles, language); setLinkedInSnapshot(value.snapshot); setLinkedInVersions((current) => [value.version, ...current.filter((item) => item.optimization_id !== value.version.optimization_id)]); } catch (error) { setNotice(linkedinError(error)); } finally { setLinkedInBusy(false); } }
  async function updateLinkedIn(snapshot: LinkedInProfileSnapshot) { const value = await api.updateLinkedInSections(snapshot.snapshot_id, snapshot.sections); setLinkedInSnapshot(value); }
  async function reparseLinkedIn() { if (!linkedInSnapshot) return; setLinkedInBusy(true); try { const value = await api.reparseLinkedIn(linkedInSnapshot.snapshot_id); setLinkedInSnapshot(value); setNotice(locale === "es" ? "Secciones de LinkedIn reanalizadas localmente." : "LinkedIn sections reparsed locally."); } catch (error) { setNotice(linkedinError(error)); } finally { setLinkedInBusy(false); } }

  function renderView(view: ViewId) {
    if (view === "profile") return <ProfileView profile={profile} profiles={profiles} profileLoadError={profileLoadError} t={t} locale={locale} onReloadProfiles={restoreProfiles} onSelectProfile={selectProfile} onCreateProfile={createProfile} onRenameProfile={renameProfile} onDuplicateProfile={duplicateProfile} onDeleteProfile={deleteProfile} onUpdatePreferences={updatePreferences} onImport={importProfile} onUpdateFact={updateFact} onConfirm={confirmProfile} onReprocess={reprocessProfile} onCloudConsent={cloudConsent} />;
    if (view === "about") return <AboutMePage locale={locale} profiles={profiles} onProfilesChanged={restoreProfiles} />;
    if (view === "applications") return <ApplicationsPage locale={locale} profiles={profiles} />;
    if (view === "search") return <SimpleSearchPage locale={locale} countries={countries} onSave={async (jobId, searchId) => { await api.saveSimpleJob({ job_id: jobId, search_id: searchId }); setNotice(locale === "es" ? "Vacante guardada en Favoritos." : "Job saved to Favorites."); }} />;
    if (view === "favorites") return <SavedJobsPage locale={locale} onNotice={setNotice} />;
    if (view === "linkedin") return <LinkedInView profiles={profiles} profile={profile} locale={locale} snapshot={linkedInSnapshot} versions={linkedInVersions} busy={linkedInBusy} onSelectProfile={selectProfile} onImportFile={importLinkedInFile} onImportText={importLinkedInText} onOptimize={optimizeLinkedIn} onSelectVersion={(version) => linkedInSnapshot && setLinkedInSnapshot(applyLinkedInOptimization(linkedInSnapshot, version))} onUpdateSections={updateLinkedIn} onReparse={reparseLinkedIn} />;
    return <SettingsView t={t} locale={locale} deepSeekStatus={deepSeekStatus} theirStackStatus={theirStackStatus}
      onSaveDeepSeek={async (key) => { setDeepSeekStatus(await api.saveDeepSeekKey(key)); }} onDeleteDeepSeek={async () => { setDeepSeekStatus(await api.deleteDeepSeekKey()); }}
      onSaveTheirStack={async (key) => { setTheirStackStatus(await api.saveTheirStackKey(key)); }} onDeleteTheirStack={async () => { setTheirStackStatus(await api.deleteTheirStackKey()); }}
      onExportData={async () => { const data = await api.exportLocalData(); const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })); const link = document.createElement("a"); link.href = url; link.download = `workspace-data-${new Date().toISOString().slice(0, 10)}.json`; link.click(); URL.revokeObjectURL(url); }}
      onDeleteData={async () => { await api.deleteLocalData(); window.location.reload(); }} />;
  }

  return <>
    {DEMO_MODE && <aside className="workspace-demo-banner" role="status">
      <strong>{locale === "es" ? "DEMO VISUAL" : "VISUAL DEMO"}</strong>
      <span>{locale === "es" ? "Datos ficticios · sin backend · no consume API keys" : "Sample data · no backend · no API keys used"}</span>
      <a href="https://github.com/AruHonshou/Workspace" target="_blank" rel="noopener noreferrer">{locale === "es" ? "Instalar Workspace ↗" : "Install Workspace ↗"}</a>
    </aside>}
    <DesktopShell locale={locale} onLocaleChange={() => setLocale(locale === "es" ? "en" : "es")}
      renderView={renderView} notice={notice} onDismissNotice={() => setNotice(null)} />
  </>;
}
