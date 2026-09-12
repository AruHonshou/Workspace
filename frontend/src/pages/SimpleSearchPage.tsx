import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { api, type SimpleSearchResult } from "../api/client";
import { CountryPicker } from "../components/GlobalViews";
import { FilterSelect } from "../components/DashboardViews";
import { SafeRichText } from "../components/SafeRichText";
import type { CountryOption, Locale } from "../types";
import { SearchArtwork, SearchBenefits } from "../components/SearchArtwork";

type Portal = "linkedin" | "indeed" | "computrabajo" | "glassdoor" | "infojobs" | "naukri" | "company" | "brete";
const globalPortals: Portal[] = ["linkedin", "indeed", "computrabajo", "glassdoor", "infojobs", "naukri", "company"];
const defaultPortals: Portal[] = ["linkedin", "indeed", "computrabajo", "glassdoor", "company"];
const portalLabels: Record<Portal, string> = { linkedin: "LinkedIn", indeed: "Indeed", computrabajo: "Computrabajo", glassdoor: "Glassdoor", infojobs: "InfoJobs", naukri: "Naukri", company: "ATS y páginas de empresa", brete: "Brete" };

export function SimpleSearchPage({ locale, countries, onSave }: {
  locale: Locale; countries: CountryOption[]; onSave: (jobId: string, searchId: string) => Promise<void>;
}) {
  const es = locale === "es";
  const [role, setRole] = useState("");
  const [country, setCountry] = useState(localStorage.getItem("amework-search-country") || "CR");
  const [period, setPeriod] = useState("7");
  const [sources, setSources] = useState<Portal[]>([...defaultPortals, "brete"]);
  const [result, setResult] = useState<SimpleSearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const restoring = useRef(true);
  const sourceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const job of result?.jobs ?? []) for (const source of job.source_portals ?? [job.source_portal ?? "Portal"]) counts.set(source, (counts.get(source) ?? 0) + 1);
    return [...counts.entries()];
  }, [result]);
  useEffect(() => {
    let active = true;
    const id = localStorage.getItem("amework-simple-search");
    if (!id) { restoring.current = false; return; }
    void api.getSimpleSearch(id).then((value) => {
      if (active && restoring.current) {
        setResult(value);
        setError(value.error || "");
      }
    })
      .catch(() => undefined).finally(() => { restoring.current = false; });
    return () => { active = false; };
  }, []);

  async function execute(action: () => Promise<SimpleSearchResult>) {
    if (inFlight.current) return;
    inFlight.current = true;
    restoring.current = false;
    setBusy(true); setError("");
    try {
      const value = await action();
      setResult(value);
      localStorage.setItem("amework-simple-search", value.search_id);
      if (value.error) setError(value.error);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { inFlight.current = false; setBusy(false); }
  }

  return <section className="simple-search">
    <header className="search-introduction"><p>{es ? "Busca inmediatamente, sin CV ni inteligencia artificial. Cada solicitud recupera una página de las fuentes disponibles." : "Search immediately, without a résumé or AI. Each request retrieves one page from the available sources."}</p><SearchArtwork /></header>
    <form onSubmit={(event) => { event.preventDefault(); void execute(() => api.simpleSearch({ role, country_code: country, window_days: Number(period) as 1 | 7 | 30, portals: sources, request_id: crypto.randomUUID(), refresh: false })); }}>
      <label className="simple-role">{es ? "¿Qué puesto buscas?" : "What job are you looking for?"}<input required minLength={2} maxLength={120} value={role} onChange={(event) => setRole(event.target.value)} placeholder="QA Engineer" /></label>
      <p className="role-expansion-note">⌁ {es ? "Workspace incluye equivalencias previsibles. Por ejemplo, QA también incluye QA Engineer, Quality Assurance, Tester y QA Automation." : "Workspace includes predictable role equivalents. For example, QA includes QA Engineer, Quality Assurance, Tester and QA Automation."}</p>
      <div className="simple-search-fields">
        <CountryPicker countries={countries} locale={locale} value={country} onChange={(value) => { setCountry(value); setSources((current) => value === "CR" ? [...new Set<Portal>([...current, "brete"])] : current.filter((item) => item !== "brete")); localStorage.setItem("amework-search-country", value); }} />
        <FilterSelect icon="◷" label={es ? "Publicado" : "Published"} ariaLabel={es ? "Antigüedad" : "Publication window"} value={period} onChange={setPeriod} options={[
          { value: "1", glyph: "◷", label: es ? "Últimas 24 horas" : "Last 24 hours" }, { value: "7", glyph: "◷", label: es ? "Últimos 7 días" : "Last 7 days" }, { value: "30", glyph: "◷", label: es ? "Últimos 30 días" : "Last 30 days" },
        ]} />
      </div>
      <fieldset><legend>{es ? "Procedencia detectada" : "Detected source"}</legend><div className="simple-source-options">{[...globalPortals, ...(country === "CR" ? ["brete" as const] : [])].map((source) => <label key={source}><input type="checkbox" checked={sources.includes(source)} onChange={(event) => setSources((current) => event.target.checked ? [...current, source] : current.filter((item) => item !== source))} />{portalLabels[source]}</label>)}</div></fieldset>
      <p className="simple-search-note">{es ? "Hasta 20 registros por página. Los portales elegidos se envían al proveedor antes de recuperar vacantes. La cobertura depende del país y del proveedor." : "Up to 20 records per page. Selected portals are sent to the provider before jobs are retrieved. Coverage varies by country and provider."}</p>
      <div className="page-tabs"><button type="submit" disabled={busy || !sources.length || role.trim().length < 2}>{busy ? (es ? "Buscando…" : "Searching…") : (es ? "Buscar" : "Search")}</button><button type="button" disabled={busy || !sources.length || role.trim().length < 2} onClick={() => void execute(() => api.simpleSearch({ role, country_code: country, window_days: Number(period) as 1 | 7 | 30, portals: sources, request_id: crypto.randomUUID(), refresh: true }))}>{es ? "Actualizar fuentes (puede consumir créditos)" : "Refresh sources (may use credits)"}</button></div>
      {country === "CR" && <p>{es ? "Brete se consulta desde sus páginas públicas oficiales, sin iniciar sesión." : "Brete is read from its official public pages without signing in."}</p>}
      <Link to="/configuracion">{es ? "Configurar TheirStack" : "Configure TheirStack"}</Link>
    </form>
    <SearchBenefits locale={locale} />
    {error && <p role="alert">{error}</p>}
    {result?.warnings.map((warning) => <p role="status" className="simple-search-warning" key={warning}>{warning}</p>)}
    {result && <section aria-label={es ? "Resultados" : "Results"}>
      <h2>{result.jobs.length} {es ? "vacantes" : "jobs"}{result.cached ? (es ? " · guardadas en este equipo" : " · cached on this device") : ""}</h2>
      <p>{es ? `Búsqueda iniciada: ${new Date(result.started_at).toLocaleString(locale)} · Excluidos por fecha o procedencia: ${result.excluded_count}` : `Search started: ${new Date(result.started_at).toLocaleString(locale)} · Excluded by date or source: ${result.excluded_count}`}</p>
      {sourceCounts.length > 0 && <div className="simple-source-summary" aria-label={es ? "Cobertura recuperada" : "Retrieved coverage"}>{sourceCounts.map(([source, count]) => <span key={source}><strong>{source}</strong> {count}</span>)}</div>}
      {!result.jobs.length && <p>{es ? "No hay vacantes válidas en las páginas recuperadas. Esto no indica que no existan en los portales." : "No valid jobs in the retrieved pages. This does not mean none exist on those portals."}</p>}
      {result.jobs.map((job) => <article className="simple-job" key={job.job_id}><header><span>{job.source_portals?.length ? job.source_portals.join(" · ") : job.source_portal}</span><h3>{job.title}</h3><p>{job.company} · {job.location}</p><time>{job.date_precision === "day" ? job.published_at.slice(0, 10) : new Date(job.published_at).toLocaleString(locale)}</time></header><details><summary>{es ? "Descripción" : "Description"}</summary><SafeRichText value={job.description} /></details><div className="page-tabs"><a href={job.url} target="_blank" rel="noopener noreferrer">{job.apply_url_type === "portal" ? (es ? "Abrir en el portal ↗" : "Open in portal ↗") : (es ? "Abrir publicación principal ↗" : "Open primary listing ↗")}</a><button type="button" disabled={busy} onClick={async () => { if (inFlight.current) return; inFlight.current = true; setBusy(true); try { await onSave(job.job_id, result.search_id); } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); } finally { inFlight.current = false; setBusy(false); } }}>{es ? "♡ Guardar" : "♡ Save"}</button></div></article>)}
      {result.next_page !== null && result.status === "completed" && <button type="button" disabled={busy} onClick={() => void execute(() => api.moreSimpleSearch(result.search_id, result.next_page!))}>{es ? "Cargar hasta 20 más · puede consumir 20 créditos" : "Load up to 20 more · may use 20 credits"}</button>}
    </section>}
  </section>;
}
