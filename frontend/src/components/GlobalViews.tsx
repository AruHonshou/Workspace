import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { localizedCountries, localizedCountryName } from "../data/countries";
import { useFloatingMenu } from "../hooks/useFloatingMenu";
import { useWorkspaceActive } from "../app/WorkspaceActivity";
import type {
  CandidateProfile,
  CountryOption,
  LinkedInOptimizationVersion,
  LinkedInProfileSnapshot,
  Locale,
} from "../types";
import { FilterSelect } from "./DashboardViews";

export function CountryPicker({
  locale,
  value,
  onChange,
  countries,
}: {
  locale: Locale;
  value: string;
  onChange: (code: string) => void;
  countries: CountryOption[];
}) {
  const [open, setOpen] = useState(false);
  const [renderOptions, setRenderOptions] = useState(false);
  const workspaceActive = useWorkspaceActive();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const combobox = useRef<HTMLDivElement>(null);
  const optionsRef = useRef<HTMLDivElement>(null);
  const normalizedCountries = useMemo(
    () => (countries.length ? countries : localizedCountries(locale)),
    [countries, locale],
  );
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase(locale);
    return normalizedCountries
      .filter(
        (item) =>
          !needle ||
          `${item.name} ${item.code}`
            .toLocaleLowerCase(locale)
            .includes(needle),
      )
      .slice(0, 80);
  }, [locale, normalizedCountries, query]);
  const selected = normalizedCountries.find((item) => item.code === value);
  const floatingMenu = useFloatingMenu({
    open: workspaceActive && renderOptions,
    triggerRef: combobox,
    minWidth: 320,
    maxWidth: 500,
    estimatedHeight: 360,
  });
  useEffect(() => {
    if (!workspaceActive) { setOpen(false); setRenderOptions(false); return; }
    const close = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!root.current?.contains(target) && !optionsRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [workspaceActive]);
  useEffect(() => {
    if (!workspaceActive) return;
    if (open) {
      setRenderOptions(true);
      return undefined;
    }
    if (!renderOptions) return undefined;
    const timer = window.setTimeout(() => setRenderOptions(false), 145);
    return () => window.clearTimeout(timer);
  }, [open, renderOptions, workspaceActive]);
  useEffect(() => {
    setActive((current) => Math.max(0, Math.min(current, filtered.length - 1)));
  }, [filtered.length]);
  useEffect(() => {
    if (!workspaceActive || !open || !filtered[active]) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const option = optionsRef.current?.querySelector<HTMLElement>(
        `#country-${filtered[active].code}`,
      );
      option?.scrollIntoView?.({ block: "nearest" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [active, filtered, open, workspaceActive]);
  return (
    <div className="country-picker" ref={root}>
      <label htmlFor="country-search">
        {locale === "es" ? "País de la búsqueda" : "Search country"}
      </label>
      <div ref={combobox} className={`country-combobox ${open ? "is-open" : ""}`}>
        <span aria-hidden="true">◎</span>
        <input
          id="country-search"
          role="combobox"
          aria-expanded={open}
          aria-controls="country-options"
          aria-autocomplete="list"
          aria-activedescendant={
            open && filtered[active]
              ? `country-${filtered[active].code}`
              : undefined
          }
          value={
            open
              ? query
              : selected
                ? `${selected.name} · ${selected.code}`
                : query
          }
          placeholder={
            locale === "es"
              ? "Escribe un país o código ISO"
              : "Type a country or ISO code"
          }
          onFocus={() => {
            setQuery("");
            setOpen(true);
            setActive(0);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActive(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setOpen(true);
              setActive((current) =>
                Math.min(current + 1, filtered.length - 1),
              );
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((current) => Math.max(current - 1, 0));
            }
            if (event.key === "Escape") setOpen(false);
            if (event.key === "Enter" && open && filtered[active]) {
              event.preventDefault();
              onChange(filtered[active].code);
              setOpen(false);
              setQuery("");
            }
          }}
        />
        <b aria-hidden="true">⌄</b>
      </div>
      {workspaceActive && renderOptions && createPortal(
        <div
          ref={optionsRef}
          id="country-options"
          role="listbox"
          aria-label={locale === "es" ? "Países" : "Countries"}
          className={`country-options is-portal is-placement-${floatingMenu.placement}${open ? " is-entering" : " is-closing"}`}
          style={floatingMenu.style}
        >
          {filtered.map((country, index) => (
            <button
              id={`country-${country.code}`}
              type="button"
              role="option"
              aria-selected={country.code === value}
              className={`${index === active ? "is-active" : ""} ${country.code === value ? "is-selected" : ""}`}
              key={country.code}
              onMouseEnter={() => setActive(index)}
              onClick={() => {
                onChange(country.code);
                setOpen(false);
                setQuery("");
              }}
            >
              <span>{country.code}</span>
              <strong>{country.name}</strong>
              {country.code === value && <b>✓</b>}
            </button>
          ))}
          {!filtered.length && (
            <p>
              {locale === "es"
                ? "No encontramos ese país."
                : "No country matches."}
            </p>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}

export function LinkedInView({
  profiles,
  profile,
  locale,
  snapshot,
  versions,
  busy,
  onSelectProfile,
  onImportFile,
  onImportText,
  onOptimize,
  onSelectVersion,
  onUpdateSections,
  onReparse,
}: {
  profiles: CandidateProfile[];
  profile: CandidateProfile;
  locale: Locale;
  snapshot: LinkedInProfileSnapshot | null;
  versions: LinkedInOptimizationVersion[];
  busy: boolean;
  onSelectProfile: (profileId: string) => Promise<void>;
  onImportFile: (file: File, language: string) => Promise<void>;
  onImportText: (text: string, language: string) => Promise<void>;
  onOptimize: (targetRoles: string[], language: string) => Promise<void>;
  onSelectVersion: (version: LinkedInOptimizationVersion) => void;
  onUpdateSections: (snapshot: LinkedInProfileSnapshot) => Promise<void>;
  onReparse: () => Promise<void>;
}) {
  const [language, setLanguage] = useState<"es" | "en">(locale);
  const [manualText, setManualText] = useState("");
  const [targetRoles, setTargetRoles] = useState(
    profile.targetRoles.join(", "),
  );
  const [draft, setDraft] = useState(snapshot);
  const [selectedVersionId, setSelectedVersionId] = useState(
    versions[0]?.optimization_id ?? "",
  );
  useEffect(() => setDraft(snapshot), [snapshot]);
  useEffect(() => {
    if (snapshot) setLanguage(snapshot.language.split("-", 1)[0] === "es" ? "es" : "en");
  }, [snapshot?.snapshot_id]);
  useEffect(
    () => setTargetRoles(profile.targetRoles.join(", ")),
    [profile.id, profile.targetRoles],
  );
  useEffect(() => {
    if (!versions.some((version) => version.optimization_id === selectedVersionId)) {
      setSelectedVersionId(versions[0]?.optimization_id ?? "");
    }
  }, [selectedVersionId, versions]);
  const completeProposal = draft?.sections
    .filter((section) => section.proposed_text)
    .map((section) => `${section.key.toUpperCase()}\n${section.proposed_text}`)
    .join("\n\n") ?? "";
  return (
    <section className="view-section linkedin-view">
      <div className="view-heading">
        <div>
          <span className="eyebrow">06 · LINKEDIN LAB</span>
          <h2>
            {locale === "es"
              ? "Generar mi perfil de LinkedIn"
              : "Generate my LinkedIn profile"}
          </h2>
          <p>
            {locale === "es"
              ? "Sube el PDF exportado por LinkedIn, elige tu perfil e idioma y genera un texto profesional listo para copiar y pegar. Nunca iniciamos sesión ni modificamos tu cuenta."
              : "Upload LinkedIn's exported PDF, choose your profile and language, then generate professional copy ready to paste. We never sign in or modify your account."}
          </p>
        </div>
      </div>
      <div className="linkedin-setup">
        <div className="linkedin-setup-control linkedin-profile-control">
          <span>
            {locale === "es" ? "Perfil profesional" : "Professional profile"}
          </span>
          <FilterSelect
            icon="in"
            label={locale === "es" ? "PERFIL VINCULADO" : "LINKED PROFILE"}
            ariaLabel={locale === "es" ? "Perfil profesional" : "Professional profile"}
            value={profile.id ?? ""}
            options={profiles.map((item) => ({ value: item.id ?? "", label: item.displayName, glyph: item.confirmed ? "✓" : "!" }))}
            onChange={(value) => void onSelectProfile(value)}
          />
        </div>
        <div className="linkedin-language-control">
          <span>
            {locale === "es" ? "Idioma de salida" : "Output language"}
          </span>
          <div role="group" aria-label={locale === "es" ? "Idioma de salida" : "Output language"}>
            <button type="button" className={language === "es" ? "active" : ""} aria-pressed={language === "es"} onClick={() => setLanguage("es")}>ES · Español</button>
            <button type="button" className={language === "en" ? "active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN · English</button>
          </div>
        </div>
        <label>
          <span>{locale === "es" ? "Roles objetivo" : "Target roles"}</span>
          <input
            value={targetRoles}
            onChange={(event) => setTargetRoles(event.target.value)}
            placeholder="QA Engineer, SDET"
          />
        </label>
      </div>
      {!snapshot ? (
        <div className="linkedin-import">
          <label className="linkedin-drop">
            <span>in</span>
            <strong>
              {locale === "es"
                ? "Importar PDF de LinkedIn"
                : "Import LinkedIn PDF"}
            </strong>
            <small>
              {locale === "es"
                ? "El archivo original permanece local"
                : "The original file stays local"}
            </small>
            <input
              type="file"
              accept=".pdf,.txt"
              disabled={!profile.id || busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void onImportFile(file, language);
              }}
            />
          </label>
          <div className="linkedin-or">
            {locale === "es" ? "O PEGA EL TEXTO" : "OR PASTE TEXT"}
          </div>
          <div className="linkedin-paste">
            <textarea
              value={manualText}
              onChange={(event) => setManualText(event.target.value)}
              placeholder={
                locale === "es"
                  ? "Titular, About, experiencia, educación, habilidades y certificaciones…"
                  : "Headline, About, experience, education, skills, and certifications…"
              }
            />
            <button
              type="button"
              disabled={!profile.id || manualText.trim().length < 20 || busy}
              onClick={() => void onImportText(manualText, language)}
            >
              {locale === "es" ? "Importar secciones" : "Import sections"}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="linkedin-actions">
            <span>
              {locale === "es"
                ? "Revisa el contenido extraído y pulsa Generar. DeepSeek lo analizará con el CV confirmado y la evidencia de Sobre mí asignada a este perfil."
                : "Review the extracted content, then press Generate. DeepSeek analyzes it with the confirmed résumé and About me evidence assigned to this profile."}
            </span>
            <button
              type="button"
              disabled={busy || !draft}
              onClick={() => draft && void onUpdateSections(draft)}
            >
              {locale === "es" ? "Guardar correcciones" : "Save corrections"}
            </button>
            {completeProposal && <button type="button" className="linkedin-copy-all" onClick={() => void navigator.clipboard.writeText(completeProposal)}>{locale === "es" ? "Copiar perfil completo" : "Copy complete profile"}</button>}
            <button type="button" disabled={busy} onClick={() => void onReparse()}>
              {locale === "es" ? "Reanalizar estructura" : "Reparse sections"}
            </button>
            <button
              type="button"
              className="primary-action"
              disabled={busy}
              onClick={() =>
                void onOptimize(
                  targetRoles
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                  language,
                )
              }
              >
              {busy
                ? <><span className="linkedin-button-spinner" aria-hidden="true" />{locale === "es" ? "Generando…" : "Generating…"}</>
                : locale === "es"
                  ? "Generar perfil"
                  : "Generate profile"}
            </button>
            <label className={`linkedin-reimport${busy ? " is-disabled" : ""}`} aria-disabled={busy}>
              {locale === "es" ? "Importar otro PDF" : "Import another PDF"}
              <input
                type="file"
                accept=".pdf,.txt"
                disabled={!profile.id || busy}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void onImportFile(file, language);
                }}
              />
            </label>
          </div>
          {versions.length > 0 && (
            <div className="linkedin-version-console">
              <div>
                <small>
                  {locale === "es"
                    ? "HISTORIAL DE PROPUESTAS"
                    : "PROPOSAL HISTORY"}
                </small>
                <strong>
                  {locale === "es"
                    ? `${versions.length} versiones conservadas`
                    : `${versions.length} versions retained`}
                </strong>
              </div>
              <FilterSelect
                icon="↺"
                label={locale === "es" ? "COMPARAR VERSIÓN" : "COMPARE VERSION"}
                ariaLabel={locale === "es" ? "Comparar versión de LinkedIn" : "Compare LinkedIn version"}
                value={selectedVersionId}
                options={versions.map((version) => ({
                  value: version.optimization_id,
                  label: `v${version.version} · ${new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(version.created_at))}`,
                  glyph: `v${version.version}`,
                }))}
                onChange={(value) => {
                  setSelectedVersionId(value);
                  const selected = versions.find(
                    (item) => item.optimization_id === value,
                  );
                  if (selected) onSelectVersion(selected);
                }}
              />
            </div>
          )}
          <div className="linkedin-sections">
            {draft?.sections.map((section, index) => (
              <article key={section.key}>
                <header>
                  <strong>{section.key}</strong>
                  <span>
                    {section.character_count ??
                      section.proposed_text?.length ??
                      section.current_text.length}{" "}
                    {locale === "es" ? "caracteres" : "characters"}
                  </span>
                </header>
                <label>
                  <span>
                    {locale === "es" ? "Contenido actual" : "Current content"}
                  </span>
                  <textarea
                    value={section.current_text}
                    onChange={(event) =>
                      setDraft((current) =>
                        current
                          ? {
                              ...current,
                              sections: current.sections.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        current_text: event.target.value,
                                      }
                                    : item,
                              ),
                            }
                          : current,
                      )
                    }
                  />
                </label>
                {section.proposed_text && (
                  <div className="linkedin-proposal">
                    <span>{locale === "es" ? "PROPUESTA" : "PROPOSAL"}</span>
                    <p>{section.proposed_text}</p>
                    {section.rationale && <small>{section.rationale}</small>}
                    {(section.evidence ?? []).length > 0 && (
                      <div className="linkedin-evidence">
                        <strong>
                          {locale === "es"
                            ? "Evidencia de tu perfil"
                            : "Evidence from your profile"}
                        </strong>
                        <ul>
                          {(section.evidence ?? []).map((evidence) => (
                            <li key={evidence}>{evidence}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div>
                      {section.keywords?.map((keyword) => (
                        <b key={keyword}>{keyword}</b>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        void navigator.clipboard.writeText(
                          section.proposed_text ?? "",
                        )
                      }
                    >
                      {locale === "es" ? "Copiar propuesta" : "Copy proposal"}
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
