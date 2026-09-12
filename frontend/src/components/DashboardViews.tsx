import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Translate } from "../i18n";
import { useFloatingMenu } from "../hooks/useFloatingMenu";
import { useWorkspaceActive } from "../app/WorkspaceActivity";
import { FactDisclosure } from "./FactDisclosure";
import type {
  CandidateProfile,
  DeepSeekStatus,
  ProfileFact,
  TheirStackStatus,
} from "../types";
type FilterOption = { value: string; label: string; glyph?: string };


function splitList(value: string): string[] {
  return [...new Set(value.split(/[,;\n]/).map((item) => item.trim()).filter(Boolean))];
}

function PreferenceListInput({ items, onChange, placeholder }: { items: string[]; onChange: (items: string[]) => void; placeholder?: string }) {
  const [value, setValue] = useState(items.join(", "));
  useEffect(() => setValue(items.join(", ")), [items]);
  return <input value={value} onChange={(event) => setValue(event.target.value)} onBlur={() => onChange(splitList(value))} placeholder={placeholder} />;
}

export function ProfileView({ profile, profiles, profileLoadError, t, locale, onReloadProfiles, onSelectProfile, onCreateProfile, onRenameProfile, onDuplicateProfile, onDeleteProfile, onUpdatePreferences, onImport, onUpdateFact, onConfirm, onReprocess, onCloudConsent }: {
  profile: CandidateProfile;
  profiles: CandidateProfile[];
  profileLoadError?: string | null;
  t: Translate;
  locale: "es" | "en";
  onReloadProfiles?: () => Promise<void>;
  onSelectProfile: (profileId: string) => Promise<void>;
  onCreateProfile: (displayName: string) => Promise<void>;
  onRenameProfile: (displayName: string) => Promise<void>;
  onDuplicateProfile: () => Promise<void>;
  onDeleteProfile: () => Promise<void>;
  onUpdatePreferences: (preferences: CandidateProfile["preferences"]) => Promise<void>;
  onImport: (file: File, language: string) => Promise<void>;
  onUpdateFact: (fact: ProfileFact, text: string) => Promise<void>;
  onConfirm: () => Promise<void>;
  onReprocess: () => Promise<void>;
  onCloudConsent: (granted: boolean) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [profileAction, setProfileAction] = useState<"create" | "rename" | "delete" | null>(null);
  const [profileName, setProfileName] = useState("");
  const [profileActionError, setProfileActionError] = useState<string | null>(null);
  const [preferenceDraft, setPreferenceDraft] = useState(profile.preferences);
  useEffect(() => setPreferenceDraft(profile.preferences), [profile.id, profile.preferences]);
  const grouped = useMemo(() => {
    const order: ProfileFact["category"][] = ["experience", "project", "skill", "education", "certification", "achievement", "preference"];
    return order
      .map((category) => ({ category, facts: profile.facts.filter((fact) => fact.category === category) }))
      .filter((group) => group.facts.length);
  }, [profile.facts]);
  const labels: Record<ProfileFact["category"], string> = locale === "es"
    ? { experience: "Experiencia", project: "Proyectos", skill: "Habilidades", education: "Educación", certification: "Certificaciones", achievement: "Logros", preference: "Preferencias" }
    : { experience: "Experience", project: "Projects", skill: "Skills", education: "Education", certification: "Certifications", achievement: "Achievements", preference: "Preferences" };
  const hasResume = Object.keys(profile.resumes).length > 0;
  const step = !hasResume ? 1 : profile.confirmed ? 3 : 2;
  const importFile = async (file: File | undefined, language: string) => {
    if (!file) return;
    setBusy(true);
    try { await onImport(file, language); } finally { setBusy(false); }
  };

  return (
    <section className="view-section career-profile">
      <div className="profile-console" aria-label={locale === "es" ? "Administrar perfiles" : "Manage profiles"}>
        <div className="profile-console-screen" data-confirmed={profile.confirmed}>
          <small>{locale === "es" ? "PERFIL ACTIVO" : "ACTIVE PROFILE"}</small>
          <strong>{profile.displayName || (locale === "es" ? "Sin perfil" : "No profile")}</strong>
          <span>{profile.confirmed ? (locale === "es" ? "LISTO PARA BUSCAR" : "READY TO SEARCH") : (locale === "es" ? "CONFIGURACIÓN PENDIENTE" : "SETUP PENDING")}</span>
        </div>
        {profiles.length > 0 && <FilterSelect compact align="end" icon="▣" label={locale === "es" ? "CAMBIAR PERFIL" : "SWITCH PROFILE"} ariaLabel={locale === "es" ? "Perfil profesional" : "Professional profile"} value={profile.id ?? ""} options={profiles.map((item) => ({ value: item.id ?? "", label: item.displayName, glyph: item.confirmed ? "✓" : "·" }))} onChange={(value) => void onSelectProfile(value)} />}
        <div className="profile-console-actions">
          <button type="button" onClick={() => { setProfileActionError(null); setProfileName(""); setProfileAction("create"); }}>＋ {locale === "es" ? "Nuevo" : "New"}</button>
          <button type="button" disabled={!profile.id} onClick={() => { setProfileActionError(null); setProfileName(profile.displayName); setProfileAction("rename"); }}>✎ {locale === "es" ? "Renombrar" : "Rename"}</button>
          <button type="button" disabled={!profile.id} onClick={() => void onDuplicateProfile()}>⧉ {locale === "es" ? "Duplicar" : "Duplicate"}</button>
          <button type="button" className="danger" disabled={!profile.id} onClick={() => { setProfileActionError(null); setProfileAction("delete"); }}>× {locale === "es" ? "Eliminar" : "Delete"}</button>
        </div>
      </div>

      {profileLoadError && <div role="alert"><span>{locale === "es" ? "No se pudieron cargar tus perfiles." : "Your profiles could not be loaded."}</span>{onReloadProfiles && <button type="button" className="text-button" disabled={busy} onClick={async () => { setBusy(true); try { await onReloadProfiles(); } catch { /* The visible alert remains until a retry succeeds. */ } finally { setBusy(false); } }}>{locale === "es" ? "Reintentar" : "Retry"}</button>}</div>}

      {profileAction && <div className={`profile-action-card ${profileAction === "delete" ? "danger" : ""}`} role="dialog" aria-modal="true" aria-label={locale === "es" ? "Administrar perfil" : "Manage profile"}>
        <div><small>{locale === "es" ? "PERFIL PROFESIONAL" : "PROFESSIONAL PROFILE"}</small><strong>{profileAction === "create" ? (locale === "es" ? "Crear perfil profesional" : "Create professional profile") : profileAction === "rename" ? (locale === "es" ? "Renombrar perfil" : "Rename profile") : (locale === "es" ? "Eliminar perfil y sus datos" : "Delete profile and its data")}</strong></div>
        {profileAction === "delete" ? <p>{locale === "es" ? `Se eliminarán los CV, hechos, análisis y documentos vinculados a “${profile.displayName}”. Tus Favoritos permanecerán guardados. Esta acción no se puede deshacer.` : `Résumés, facts, analyses, and documents linked to “${profile.displayName}” will be deleted. Your Favorites remain saved. This cannot be undone.`}</p> : <input autoFocus maxLength={60} value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder={locale === "es" ? "Ej. QA Automation" : "e.g. QA Automation"} />}
        {profileActionError && <p role="alert">{profileActionError}</p>}
        <div><button type="button" className={profileAction === "delete" ? "danger-button" : "primary-action"} disabled={busy || (profileAction !== "delete" && profileName.trim().length < 2)} onClick={async () => { setBusy(true); setProfileActionError(null); try { if (profileAction === "create") await onCreateProfile(profileName.trim()); else if (profileAction === "rename") await onRenameProfile(profileName.trim()); else await onDeleteProfile(); setProfileAction(null); } catch (error) { setProfileActionError(error instanceof Error ? error.message : String(error)); } finally { setBusy(false); } }}>{profileAction === "delete" ? (locale === "es" ? "Sí, eliminar" : "Yes, delete") : (locale === "es" ? "Guardar" : "Save")}</button><button type="button" className="text-button" disabled={busy} onClick={() => setProfileAction(null)}>{t("common.cancel")}</button></div>
      </div>}

      <div className="view-heading">
        <div>
          <span className="eyebrow">01 · {locale === "es" ? "Tu historia profesional" : "Your professional story"}</span>
          <h2>{t("profile.title")}</h2>
          <p>{locale === "es" ? "Convierte tu CV en hechos verificables. Las herramientas de IA sólo podrán usar aquello que confirmes." : "Turn your résumé into verifiable facts. AI tools can only use what you confirm."}</p>
        </div>
        <span className={`profile-state ${profile.confirmed ? "confirmed" : "pending"}`}>{profile.confirmed ? t("profile.confirmed") : t("profile.pending")}</span>
      </div>

      <ol className="profile-steps" aria-label={locale === "es" ? "Progreso del CV" : "Résumé progress"}>
        {[locale === "es" ? "Importar" : "Import", locale === "es" ? "Revisar" : "Review", locale === "es" ? "Confirmar" : "Confirm"].map((label, index) => (
          <li key={label} className={step >= index + 1 ? "active" : ""} data-step={profile.confirmed || step > index + 1 ? "completed" : step === index + 1 ? "current" : "pending"} aria-current={!profile.confirmed && step === index + 1 ? "step" : undefined}>
            <span>{profile.confirmed || step > index + 1 ? "✓" : index + 1}</span><strong>{label}</strong>
          </li>
        ))}
      </ol>

      <div className="resume-language-intro"><strong>{locale === "es" ? "Elige el CV que representa este perfil" : "Choose the résumé that represents this profile"}</strong><span>{locale === "es" ? "Puedes mantener una versión en español, en inglés o ambas. Cada documento se revisa de forma independiente." : "You can keep a Spanish version, an English version, or both. Each document is reviewed independently."}</span></div>
      <div className="bilingual-resumes">
        {(["es", "en"] as const).map((language) => {
          const resume = profile.resumes[language] ?? Object.entries(profile.resumes).find(([key]) => key.split("-", 1)[0] === language)?.[1];
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
          {profile.confirmed && profile.redactedPreview && <section className={`cloud-consent-card ${profile.cloudConsentValid ? "is-granted" : ""}`}>
            <header><span aria-hidden="true">{profile.cloudConsentValid ? "✓" : "☁"}</span><div><small>DEEPSEEK · {locale === "es" ? "CONSENTIMIENTO EXPLÍCITO" : "EXPLICIT CONSENT"}</small><strong>{profile.cloudConsentValid ? (locale === "es" ? "Procesamiento seguro habilitado" : "Safe processing enabled") : (locale === "es" ? "Revisa qué datos pueden enviarse" : "Review what may be sent")}</strong></div></header>
            <p>{locale === "es" ? "El PDF original, correo y teléfono nunca se envían. Sólo esta vista profesional redactada se usará para análisis y documentos que tú solicites." : "The original file, email, and phone are never sent. Only this redacted professional preview is used for analyses and documents you request."}</p>
            <details><summary>{locale === "es" ? "Ver vista exacta para DeepSeek" : "View the exact DeepSeek preview"}</summary><pre>{profile.redactedPreview.redacted_text}</pre></details>
            <div className="cloud-consent-actions">
              {!profile.cloudConsentValid && <button type="button" className="primary-action" disabled={busy} onClick={async () => { setBusy(true); try { await onCloudConsent(true); } finally { setBusy(false); } }}>{locale === "es" ? "Acepto usar esta vista" : "I approve this preview"}</button>}
              {profile.cloudConsentValid && <button type="button" className="secondary-button" disabled={busy} onClick={async () => { setBusy(true); try { await onCloudConsent(false); } finally { setBusy(false); } }}>{locale === "es" ? "Revocar consentimiento" : "Revoke consent"}</button>}
              <span>{locale === "es" ? "Puedes cambiar esta decisión cuando quieras." : "You can change this decision at any time."}</span>
            </div>
          </section>}
          <details className="profile-preferences">
            <summary><span>⌁</span><div><strong>{locale === "es" ? "Preferencias y filtro seguro" : "Preferences and safe filter"}</strong><small>{locale === "es" ? "Sólo separan incompatibilidades explícitas; una tecnología ausente nunca oculta una vacante." : "Only explicit conflicts are separated; a missing technology never hides a job."}</small></div></summary>
            <div className="preference-grid">
              <label><span>{locale === "es" ? "Roles objetivo" : "Target roles"}</span><PreferenceListInput items={preferenceDraft.desiredTitles} onChange={(items) => setPreferenceDraft({ ...preferenceDraft, desiredTitles: items })} placeholder="QA Engineer, SDET" /></label>
              <label><span>{locale === "es" ? "Ubicaciones aceptadas" : "Accepted locations"}</span><PreferenceListInput items={preferenceDraft.desiredLocations} onChange={(items) => setPreferenceDraft({ ...preferenceDraft, desiredLocations: items })} placeholder="Bogotá, Remote worldwide" /></label>
              <fieldset><legend>{locale === "es" ? "Seniority" : "Seniority"}</legend>{["internship", "entry", "junior", "mid", "senior", "lead", "manager", "director", "executive"].map((value) => <label key={value}><input type="checkbox" checked={preferenceDraft.targetSeniorities.includes(value)} onChange={(event) => setPreferenceDraft({ ...preferenceDraft, targetSeniorities: event.target.checked ? [...preferenceDraft.targetSeniorities, value] : preferenceDraft.targetSeniorities.filter((item) => item !== value) })} />{value}</label>)}</fieldset>
              <fieldset><legend>{locale === "es" ? "Modalidades" : "Work modes"}</legend>{(["remote", "hybrid", "onsite"] as const).map((value) => <label key={value}><input type="checkbox" checked={preferenceDraft.allowedWorkModes.includes(value)} onChange={(event) => setPreferenceDraft({ ...preferenceDraft, allowedWorkModes: event.target.checked ? [...preferenceDraft.allowedWorkModes, value] : preferenceDraft.allowedWorkModes.filter((item) => item !== value) })} />{value === "onsite" ? (locale === "es" ? "presencial" : "on-site") : value === "hybrid" ? (locale === "es" ? "híbrido" : "hybrid") : (locale === "es" ? "remoto" : "remote")}</label>)}</fieldset>
              <label><span>{locale === "es" ? "Palabras excluidas" : "Excluded keywords"}</span><PreferenceListInput items={preferenceDraft.excludedKeywords} onChange={(items) => setPreferenceDraft({ ...preferenceDraft, excludedKeywords: items })} placeholder={locale === "es" ? "ventas, guardias" : "sales, on-call"} /></label>
              <label><span>{locale === "es" ? "Sectores excluidos" : "Excluded sectors"}</span><PreferenceListInput items={preferenceDraft.excludedSectors} onChange={(items) => setPreferenceDraft({ ...preferenceDraft, excludedSectors: items })} placeholder={locale === "es" ? "apuestas" : "gambling"} /></label>
            </div>
            <button type="button" className="secondary-button" onClick={() => void onUpdatePreferences(preferenceDraft)}>{locale === "es" ? "Guardar preferencias" : "Save preferences"}</button>
          </details>
          <div className="fact-groups">
            {grouped.map((group) => (
              <FactDisclosure key={`${profile.id}-${group.category}`} title={labels[group.category]} verified={group.facts.filter((fact) => fact.verified).length} locale={locale}>
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
              </FactDisclosure>
            ))}
          </div>
          <div className="profile-actions">
            {hasResume && <button type="button" className="secondary-button" disabled={busy} onClick={async () => { const accepted = window.confirm(locale === "es" ? "Se reagruparán los hechos extraídos y tendrás que revisarlos y confirmar nuevamente el perfil. Tus archivos originales se conservarán. ¿Continuar?" : "Extracted facts will be regrouped and you will need to review and confirm the profile again. Your original files will be preserved. Continue?"); if (!accepted) return; setBusy(true); try { await onReprocess(); } finally { setBusy(false); } }}>{locale === "es" ? "Optimizar extracción" : "Optimize extraction"}</button>}
            {!profile.confirmed && <button type="button" className="primary-action" disabled={busy || profile.facts.length === 0 || !hasResume} onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}>{busy ? t("profile.confirming") : t("profile.confirm")}</button>}
            {!hasResume && <span className="profile-requirement">{locale === "es" ? "Importa un CV en español o inglés para confirmar el perfil." : "Upload a Spanish or English résumé to confirm the profile."}</span>}
          </div>
        </>
      )}
    </section>
  );
}


export function FilterSelect({ icon, label, ariaLabel, value, options, onChange, layout = "floating", disabled = false, compact = false, align = "start" }: {
  icon: string;
  label: string;
  ariaLabel: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  layout?: "floating" | "inline";
  disabled?: boolean;
  compact?: boolean;
  align?: "start" | "end";
}) {
  const [open, setOpen] = useState(false);
  const [renderMenu, setRenderMenu] = useState(false);
  const workspaceActive = useWorkspaceActive();
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const matchedIndex = options.findIndex((option) => option.value === value);
  const selectedIndex = Math.max(0, matchedIndex);
  const hasSelection = matchedIndex >= 0 && value !== "";
  const selected = hasSelection
    ? options[matchedIndex]
    : { value: "", label: "Seleccionar…", glyph: "·" };
  const floatingMenu = useFloatingMenu({
    open: workspaceActive && renderMenu && layout === "floating",
    triggerRef,
    minWidth: compact ? 224 : 248,
    maxWidth: compact ? 300 : 440,
    estimatedHeight: Math.min(compact ? 250 : 370, 50 + options.length * (compact ? 38 : 46)),
    align,
  });

  useEffect(() => {
    if (!workspaceActive) { setOpen(false); setRenderMenu(false); return; }
    if (!open) return undefined;
    const closeOutside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    menuRef.current?.focus();
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, [open, workspaceActive]);
  useEffect(() => {
    if (!workspaceActive) return;
    if (open) {
      setRenderMenu(true);
      const frame = window.requestAnimationFrame(() => menuRef.current?.focus());
      return () => window.cancelAnimationFrame(frame);
    }
    if (!renderMenu) return undefined;
    const timer = window.setTimeout(() => setRenderMenu(false), 145);
    return () => window.clearTimeout(timer);
  }, [open, renderMenu, workspaceActive]);
  useEffect(() => {
    if (!workspaceActive || !open || !options[activeIndex]) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const option = menuRef.current
        ?.querySelectorAll<HTMLElement>('[role="option"]')[activeIndex];
      option?.scrollIntoView?.({ block: "nearest" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeIndex, menuId, open, options, workspaceActive]);

  const openMenu = (index = selectedIndex) => {
    if (!options.length) return;
    setActiveIndex(index);
    setOpen(true);
  };
  const choose = (option: FilterOption) => {
    onChange(option.value);
    setOpen(false);
    triggerRef.current?.focus();
  };
  const move = (direction: number) => {
    setActiveIndex((current) => (current + direction + options.length) % options.length);
  };

  const menu = workspaceActive && renderMenu ? (
    <div
      ref={menuRef}
      id={menuId}
      className={`filter-menu${layout === "floating" ? " is-portal" : ""}${compact ? " is-compact" : ""} is-placement-${floatingMenu.placement}${open ? " is-entering" : " is-closing"}`}
      style={layout === "floating" ? floatingMenu.style : undefined}
      role="listbox"
      aria-label={ariaLabel}
      aria-activedescendant={`${menuId}-option-${activeIndex}`}
      tabIndex={-1}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown") { event.preventDefault(); move(1); }
        else if (event.key === "ArrowUp") { event.preventDefault(); move(-1); }
        else if (event.key === "Home") { event.preventDefault(); setActiveIndex(0); }
        else if (event.key === "End") { event.preventDefault(); setActiveIndex(options.length - 1); }
        else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(options[activeIndex]); }
        else if (event.key === "Escape") { event.preventDefault(); setOpen(false); triggerRef.current?.focus(); }
        else if (event.key === "Tab") setOpen(false);
      }}
    >
      <span className="filter-menu-caption" aria-hidden="true">{label}</span>
      {options.map((option, index) => (
        <button
          id={`${menuId}-option-${index}`}
          type="button"
          role="option"
          aria-selected={option.value === value}
          className={`${option.value === value ? "is-selected" : ""}${index === activeIndex ? " is-active" : ""}`}
          key={option.value}
          onPointerEnter={() => setActiveIndex(index)}
          onClick={() => choose(option)}
        >
          <span className="filter-option-glyph" aria-hidden="true">{option.glyph}</span>
          <span>{option.label}</span>
          <b aria-hidden="true">{option.value === value ? "✓" : ""}</b>
        </button>
      ))}
    </div>
  ) : null;

  return (
    <div ref={rootRef} className={`filter-select is-${layout}${open ? " is-open" : ""}${hasSelection && value !== "all" ? " has-value" : ""}`}>
      <button
        ref={triggerRef}
        type="button"
        className="filter-control"
        disabled={disabled || !options.length}
        aria-label={`${ariaLabel}: ${selected.label}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => open ? setOpen(false) : openMenu()}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (!open) openMenu(event.key === "ArrowDown" ? selectedIndex : Math.max(0, selectedIndex - 1));
            else move(event.key === "ArrowDown" ? 1 : -1);
          }
          else if (open && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); choose(options[activeIndex]); }
          else if (open && event.key === "Escape") { event.preventDefault(); setOpen(false); }
        }}
      >
        <span className="filter-control-icon" aria-hidden="true">{icon}</span>
        <span className="filter-control-copy"><small>{label}</small><strong>{selected.label}</strong></span>
        <span className="filter-chevron" aria-hidden="true">⌄</span>
      </button>
      {menu && (layout === "floating" ? createPortal(menu, document.body) : menu)}
    </div>
  );
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

export function SettingsView({ t, locale, deepSeekStatus, theirStackStatus, onSaveDeepSeek, onDeleteDeepSeek, onSaveTheirStack, onDeleteTheirStack, onExportData, onDeleteData }: {
  t: Translate;
  locale: "es" | "en";
  deepSeekStatus: DeepSeekStatus | null;
  theirStackStatus: TheirStackStatus | null;
  onSaveDeepSeek: (key: string) => Promise<void>;
  onDeleteDeepSeek: () => Promise<void>;
  onSaveTheirStack: (key: string) => Promise<void>;
  onDeleteTheirStack: () => Promise<void>;
  onExportData: () => Promise<void>;
  onDeleteData: () => Promise<void>;
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
  return <section className="view-section settings-view">
    <div className="view-heading"><div><span className="eyebrow">{locale === "es" ? "Conexiones y privacidad" : "Connections and privacy"}</span><h2>{t("settings.title")}</h2><p>{locale === "es" ? "Las claves se validan y guardan en el almacén seguro del sistema operativo; nunca regresan al navegador." : "Keys are validated and stored in the operating system secure vault; they are never returned to the browser."}</p></div></div>
    {error && <div className="inline-warning">{error}</div>}
    <div className="provider-grid">
      <ProviderKeyCard provider="TheirStack" locale={locale} description={locale === "es" ? "Proveedor principal de búsqueda por país" : "Primary country-based search provider"} configured={Boolean(theirStackStatus?.configured)} keyValue={theirStackKey} setKeyValue={setTheirStackKey} busy={busy === "theirstack"} onSave={() => perform("theirstack", async () => { await onSaveTheirStack(theirStackKey); setTheirStackKey(""); })} onDelete={() => perform("theirstack", onDeleteTheirStack)} note={locale === "es" ? "Hasta 20 vacantes por página. Cada resultado devuelto puede consumir un crédito." : "Up to 20 jobs per page. Each returned result may consume one credit."} statusDetail={creditStatus} />
      <ProviderKeyCard provider="DeepSeek" locale={locale} description={locale === "es" ? "Análisis, CV ATS, guías y LinkedIn" : "Analysis, ATS résumés, guides, and LinkedIn"} configured={Boolean(deepSeekStatus?.configured)} keyValue={deepSeekKey} setKeyValue={setDeepSeekKey} busy={busy === "deepseek"} onSave={() => perform("deepseek", async () => { await onSaveDeepSeek(deepSeekKey); setDeepSeekKey(""); })} onDelete={() => perform("deepseek", onDeleteDeepSeek)} note={locale === "es" ? "Sólo recibe hechos profesionales confirmados y redactados, nunca el PDF original ni datos de contacto." : "Receives only redacted, confirmed professional facts—never the original PDF or contact details."} statusDetail={deepSeekStatus?.configured ? (locale === "es" ? "Conexión validada" : "Connection validated") : undefined} />
    </div>
    <section className="local-data-console"><header><span>DATA://LOCAL</span><div><strong>{locale === "es" ? "Tus datos, bajo tu control" : "Your data, under your control"}</strong><p>{locale === "es" ? "Exporta una copia JSON o elimina perfiles, búsquedas, favoritos y documentos locales." : "Export a JSON copy or delete local profiles, searches, favorites, and documents."}</p></div></header><div><button type="button" disabled={busy !== null} onClick={() => void perform("export-data", onExportData)}>{locale === "es" ? "Exportar mis datos" : "Export my data"}</button><div className="danger-zone"><strong>{locale === "es" ? "Zona de riesgo" : "Danger zone"}</strong><button type="button" className="danger-button" disabled={busy !== null} onClick={() => { const approved = window.confirm(locale === "es" ? "Esto eliminará permanentemente todos los datos locales de Workspace. Las claves del sistema operativo no se eliminan. ¿Continuar?" : "This permanently deletes all local Workspace data. Operating-system credentials are not deleted. Continue?"); if (approved) void perform("delete-data", onDeleteData); }}>{locale === "es" ? "Borrar todos los datos" : "Delete all data"}</button></div></div></section>
    <div className="settings-cards"><article><span>⌂</span><div><strong>{t("settings.cvTitle")}</strong><p>{locale === "es" ? "El CV original, la base de datos y las guías permanecen en este equipo." : "The original résumé, database, and guides remain on this computer."}</p></div></article><article><span>↗</span><div><strong>{t("settings.applicationsTitle")}</strong><p>{t("settings.applications")}</p></div></article></div>
  </section>;
}
