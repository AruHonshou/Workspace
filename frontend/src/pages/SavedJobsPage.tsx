import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type SavedJob } from "../api/client";
import { useWorkspaceActive } from "../app/WorkspaceActivity";
import { WorkspaceIcon } from "../app/WorkspaceIcon";
import { SafeRichText } from "../components/SafeRichText";
import type { Locale } from "../types";

export function SavedJobsPage({ locale, onNotice }: { locale: Locale; onNotice?: (message: string) => void }) {
  const es = locale === "es";
  const workspaceActive = useWorkspaceActive();
  const [items, setItems] = useState<SavedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceActive) return;
    let active = true;
    void api.listSavedJobs().then((value) => { if (active) { setItems(value); setError(""); } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : String(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [workspaceActive]);

  async function remove(item: SavedJob) {
    if (removing) return;
    const savedId = item.saved_id ?? item.job_id;
    setRemoving(savedId);
    try {
      await api.deleteSavedJob(savedId);
      setItems((current) => current.filter((saved) => (saved.saved_id ?? saved.job_id) !== savedId));
      onNotice?.(es ? "Vacante quitada de Favoritos." : "Job removed from Favorites.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setRemoving(null); }
  }

  if (loading) return <p className="ui-loading" role="status">{es ? "Cargando favoritos…" : "Loading favorites…"}</p>;
  return <section className="saved-jobs" aria-label={es ? "Vacantes guardadas" : "Saved jobs"}>
    <header className="saved-jobs-intro">
      <span className="hero-icon" aria-hidden="true"><WorkspaceIcon name="favorites" /></span>
      <div><span className="section-kicker">WORKSPACE / SAVED</span><h2>{es ? "Tus vacantes guardadas" : "Your saved jobs"}</h2><p>{es ? "Guarda primero; elige un perfil sólo cuando quieras analizar una oferta." : "Save first; choose a profile only when you want to analyze a job."}</p></div>
      <span className="hero-count">{items.length} {es ? "guardadas" : "saved"}</span>
    </header>
    {error && <p role="alert">{error}</p>}
    {!items.length && !error && <div className="saved-jobs-empty"><span className="ui-empty-icon"><WorkspaceIcon name="favorites" /></span><strong>{es ? "Aún no hay favoritos" : "No favorites yet"}</strong><p>{es ? "Vuelve a Buscar empleos y pulsa ♡ Guardar en una vacante." : "Return to Find jobs and press ♡ Save on a vacancy."}</p></div>}
    <div className="saved-jobs-grid">{items.map((item) => { const savedId = item.saved_id ?? item.job_id; return <article className="saved-job-card" key={savedId}>
      <header><span className="job-source-label"><WorkspaceIcon name={item.source_portals?.some((portal) => portal.toLowerCase() === "linkedin") ? "linkedin" : "search"} />{item.source_portals?.join(" · ") || (es ? "Portal" : "Portal")}</span><time>{item.created_at ? new Date(item.created_at).toLocaleDateString(locale) : ""}</time></header>
      <h3><Link className="saved-job-title" to={`/favoritos/${encodeURIComponent(savedId)}`}>{item.title}</Link></h3><p className="saved-job-company">{item.company} · {item.location || (es ? "Ubicación no indicada" : "Location not specified")}</p>
      <SafeRichText className="saved-job-description" value={item.description.slice(0, 240)} />
      <div className="saved-job-actions"><a href={item.apply_url} target="_blank" rel="noopener noreferrer">{item.apply_url_type === "portal" ? (es ? "Abrir portal ↗" : "Open portal ↗") : (es ? "Abrir publicación ↗" : "Open listing ↗")}</a><button type="button" disabled={removing === savedId} onClick={() => void remove(item)}>{removing === savedId ? "…" : (es ? "Quitar" : "Remove")}</button></div>
    </article>; })}</div>
  </section>;
}
