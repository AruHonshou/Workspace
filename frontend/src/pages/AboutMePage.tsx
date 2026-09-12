import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { FilterSelect } from "../components/DashboardViews";
import type { AboutMeCategory, AboutMeEntry, AboutMeProfile, CandidateProfile, Locale } from "../types";

const EMPTY_CONTACT: AboutMeProfile["contact"] = {
  full_name: "", emails: [], phones: [], address_lines: [], city: "", region: "",
  country_code: null, postal_code: "", websites: [], legacy_values: [],
};

const categories: AboutMeCategory[] = ["experience", "project", "skill", "education", "certification", "achievement"];

function list(value: string): string[] {
  return [...new Set(value.split(/[;,\n]/).map((item) => item.trim()).filter(Boolean))];
}

export function AboutMePage({ locale, profiles, onProfilesChanged }: { locale: Locale; profiles: CandidateProfile[]; onProfilesChanged?: () => Promise<void> }) {
  const es = locale === "es";
  const [value, setValue] = useState<AboutMeProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const labels = useMemo<Record<AboutMeCategory, string>>(() => es ? {
    experience: "Experiencia", project: "Proyecto", skill: "Tecnología o habilidad",
    education: "Educación", certification: "Certificación", achievement: "Logro",
  } : {
    experience: "Experience", project: "Project", skill: "Technology or skill",
    education: "Education", certification: "Certification", achievement: "Achievement",
  }, [es]);

  useEffect(() => {
    let active = true;
    void api.getAboutMe().then((result) => { if (active) setValue(result); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { active = false; };
  }, []);

  function contact(patch: Partial<AboutMeProfile["contact"]>) {
    setValue((current) => current ? { ...current, contact: { ...current.contact, ...patch } } : current);
  }

  function entry(id: string, patch: Partial<AboutMeEntry>) {
    setValue((current) => current ? { ...current, entries: current.entries.map((item) => item.entry_id === id ? { ...item, ...patch } : item) } : current);
  }

  function addEntry() {
    const now = new Date().toISOString();
    const next: AboutMeEntry = {
      entry_id: `about_${crypto.randomUUID().replaceAll("-", "")}`,
      category: "experience", title: "", details: "", language: locale,
      profile_ids: profiles.map((profile) => profile.id).filter((id): id is string => Boolean(id)),
      verified: true, created_at: now, updated_at: now,
    };
    setValue((current) => current ? { ...current, entries: [...current.entries, next] } : current);
  }

  async function save() {
    if (!value || busy) return;
    const invalid = value.entries.find((item) => !item.title.trim() || !item.details.trim());
    if (invalid) { setError(es ? "Completa el título y detalle de cada elemento." : "Complete every item title and detail."); return; }
    setBusy(true); setError(""); setSaved(false);
    try {
      const stored = await api.saveAboutMe({ contact: value.contact, entries: value.entries });
      setValue(stored); setSaved(true);
      await onProfilesChanged?.();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }

  if (!value) return <p role="status">{error || (es ? "Cargando tu información profesional…" : "Loading your professional information…")}</p>;
  return <section className="about-me-page">
    <header className="page-feature-hero"><span>WORKSPACE / DOSSIER</span><h2>{es ? "Todo lo que sí puedes demostrar" : "Everything you can substantiate"}</h2><p>{es ? "Completa una vez tus proyectos, experiencia, estudios, tecnologías y certificaciones. Workspace sólo usará cada dato en los perfiles que selecciones." : "Record projects, experience, studies, technologies and certifications once. Workspace only uses each item with the profiles you select."}</p></header>

    <section className="about-contact-card">
      <header><div><small>{es ? "DATOS LOCALES" : "LOCAL DETAILS"}</small><h3>{es ? "Identidad y contacto" : "Identity and contact"}</h3></div><span>⌂ {es ? "No se envían a DeepSeek" : "Never sent to DeepSeek"}</span></header>
      <div className="about-contact-grid">
        <fieldset className="about-field-group about-field-group--identity">
          <legend>{es ? "Identidad" : "Identity"}</legend>
          <label><span>{es ? "Nombre completo" : "Full name"}</span><input value={value.contact.full_name ?? ""} onChange={(e) => contact({ full_name: e.target.value })} /></label>
        </fieldset>
        <fieldset className="about-field-group about-field-group--contact">
          <legend>{es ? "Contacto" : "Contact"}</legend>
          <label><span>Email</span><input type="email" value={value.contact.emails[0] ?? ""} onChange={(e) => contact({ emails: e.target.value ? [e.target.value] : [] })} /></label>
          <label><span>{es ? "Teléfono" : "Phone"}</span><input value={value.contact.phones[0] ?? ""} onChange={(e) => contact({ phones: e.target.value ? [e.target.value] : [] })} /></label>
        </fieldset>
        <fieldset className="about-field-group about-field-group--location">
          <legend>{es ? "Ubicación" : "Location"}</legend>
          <label><span>{es ? "Ciudad" : "City"}</span><input value={value.contact.city ?? ""} onChange={(e) => contact({ city: e.target.value })} /></label>
          <label><span>{es ? "Región/provincia" : "Region/state"}</span><input value={value.contact.region ?? ""} onChange={(e) => contact({ region: e.target.value })} /></label>
          <label><span>{es ? "País (ISO)" : "Country (ISO)"}</span><input maxLength={2} value={value.contact.country_code ?? ""} onChange={(e) => contact({ country_code: e.target.value ? e.target.value.toUpperCase() : null })} placeholder="CR" /></label>
        </fieldset>
        <fieldset className="about-field-group about-field-group--links">
          <legend>{es ? "Enlaces" : "Links"}</legend>
          <label className="wide"><span>{es ? "Portafolio, GitHub y otros enlaces" : "Portfolio, GitHub and other links"}</span><input value={value.contact.websites.join(", ")} onChange={(e) => contact({ websites: list(e.target.value) })} placeholder="https://github.com/…" /></label>
        </fieldset>
      </div>
    </section>

    <section className="about-evidence-section">
      <header><div><small>{es ? "EVIDENCIA PROFESIONAL" : "PROFESSIONAL EVIDENCE"}</small><h3>{es ? "Tu banco de información" : "Your information bank"}</h3></div><button type="button" onClick={addEntry}>＋ {es ? "Añadir información" : "Add information"}</button></header>
      {!value.entries.length && <div className="about-empty"><strong>{es ? "Añade aquello que no cabe bien en tu CV" : "Add what does not fit neatly in your résumé"}</strong><p>{es ? "Proyectos, resultados, certificaciones, estudios o herramientas que realmente conoces." : "Projects, results, certifications, studies or tools you genuinely know."}</p></div>}
      <div className="about-entry-list">{value.entries.map((item, index) => <article key={item.entry_id} className="about-entry-card">
        <header><span>{String(index + 1).padStart(2, "0")}</span><FilterSelect icon="≡" label={es ? "Categoría" : "Category"} ariaLabel={es ? "Tipo de información" : "Information type"} value={item.category} onChange={(category) => entry(item.entry_id, { category: category as AboutMeCategory })} options={categories.map((category) => ({ value: category, label: labels[category] }))} /><div className="language-switch"><button type="button" className={item.language === "es" ? "active" : ""} aria-pressed={item.language === "es"} onClick={() => entry(item.entry_id, { language: "es" })}>ES</button><button type="button" className={item.language === "en" ? "active" : ""} aria-pressed={item.language === "en"} onClick={() => entry(item.entry_id, { language: "en" })}>EN</button></div><button type="button" className="remove" aria-label={es ? "Quitar información" : "Remove information"} onClick={() => setValue({ ...value, entries: value.entries.filter((entryValue) => entryValue.entry_id !== item.entry_id) })}>×</button></header>
        <label><span>{es ? "Título claro" : "Clear title"}</span><input value={item.title} onChange={(e) => entry(item.entry_id, { title: e.target.value })} placeholder={es ? "Ej. Automatización con Playwright" : "e.g. Playwright automation"} /></label>
        <label><span>{es ? "Detalle verificable" : "Verifiable detail"}</span><textarea value={item.details} onChange={(e) => entry(item.entry_id, { details: e.target.value })} placeholder={es ? "Qué hiciste, dónde, con qué tecnologías y qué resultado obtuviste." : "What you did, where, with which technologies and the result."} /></label>
        <label><span>{es ? "Enlace opcional" : "Optional link"}</span><input type="url" value={item.url ?? ""} onChange={(e) => entry(item.entry_id, { url: e.target.value || null })} placeholder="https://…" /></label>
        <fieldset><legend>{es ? "Usar esta evidencia en" : "Use this evidence with"}</legend>{profiles.map((profile) => profile.id && <label key={profile.id}><input type="checkbox" checked={item.profile_ids.includes(profile.id)} onChange={(e) => entry(item.entry_id, { profile_ids: e.target.checked ? [...item.profile_ids, profile.id!] : item.profile_ids.filter((id) => id !== profile.id) })} /><span>{profile.displayName}</span></label>)}</fieldset>
      </article>)}</div>
    </section>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="about-save-bar"><div><strong>{saved ? (es ? "Cambios guardados" : "Changes saved") : (es ? "Listo para guardar" : "Ready to save")}</strong><small>{es ? "Al cambiar evidencia, Workspace te pedirá renovar el consentimiento de los perfiles afectados." : "When evidence changes, Workspace asks you to renew consent for affected profiles."}</small></div><button type="button" disabled={busy} onClick={() => void save()}>{busy ? (es ? "Guardando…" : "Saving…") : (es ? "Guardar Sobre mí" : "Save About me")}</button></div>
  </section>;
}
