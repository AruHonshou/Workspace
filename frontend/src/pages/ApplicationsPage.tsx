import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { FilterSelect } from "../components/DashboardViews";
import { useWorkspaceActive } from "../app/WorkspaceActivity";
import type { ApplicationStatus, CandidateProfile, JobApplication, Locale } from "../types";

const statusOrder: ApplicationStatus[] = ["applied", "contacted", "screening", "interview", "technical_test", "offer", "hired", "rejected", "no_response", "withdrawn"];

export function ApplicationsPage({ locale, profiles }: { locale: Locale; profiles: CandidateProfile[] }) {
  const es = locale === "es";
  const workspaceActive = useWorkspaceActive();
  const [items, setItems] = useState<JobApplication[]>([]);
  const [filter, setFilter] = useState<ApplicationStatus | "all">("all");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const labels = useMemo<Record<ApplicationStatus, string>>(() => es ? {
    applied: "Postulado", contacted: "Contactado", screening: "Revisión inicial", interview: "Entrevista",
    technical_test: "Prueba técnica", offer: "Oferta", hired: "Contratado", rejected: "Rechazado",
    no_response: "Sin respuesta", withdrawn: "Retirado",
  } : {
    applied: "Applied", contacted: "Contacted", screening: "Screening", interview: "Interview",
    technical_test: "Technical test", offer: "Offer", hired: "Hired", rejected: "Rejected",
    no_response: "No response", withdrawn: "Withdrawn",
  }, [es]);
  useEffect(() => {
    if (!workspaceActive) return;
    let active = true;
    void api.listApplications().then((value) => { if (active) { setItems(value); setError(""); } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { active = false; };
  }, [workspaceActive]);
  const visible = filter === "all" ? items : items.filter((item) => item.status === filter);
  const profileName = (id: string) => profiles.find((profile) => profile.id === id)?.displayName ?? (es ? "Perfil eliminado" : "Deleted profile");

  async function update(item: JobApplication, patch: { status?: ApplicationStatus; notes?: string }) {
    if (busy) return;
    setBusy(item.application_id); setError("");
    try { const stored = await api.updateApplication(item.application_id, patch); setItems((current) => current.map((value) => value.application_id === stored.application_id ? stored : value)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(""); }
  }

  return <section className="applications-page">
    <header className="page-feature-hero"><span>WORKSPACE / TRACKER</span><h2>{es ? "Tu camino de candidaturas" : "Your application journey"}</h2><p>{es ? "Registra manualmente cada avance. Workspace no entra a portales, no lee correos y nunca postula por ti." : "Record each step manually. Workspace does not sign in to portals, read email or apply for you."}</p></header>
    <div className="application-filters" role="group" aria-label={es ? "Filtrar por estado" : "Filter by status"}><button type="button" className={filter === "all" ? "active" : ""} data-status="all" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>{es ? "Todas" : "All"}<b>{items.length}</b></button>{statusOrder.map((status) => <button type="button" className={filter === status ? "active" : ""} data-status={status} aria-pressed={filter === status} key={status} onClick={() => setFilter(status)}>{labels[status]}<b>{items.filter((item) => item.status === status).length}</b></button>)}</div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {!visible.length && <div className="saved-jobs-empty"><strong>{es ? "No hay candidaturas en este estado" : "No applications in this stage"}</strong><p>{es ? "Desde un favorito, pulsa Marcar como postulado para iniciar su seguimiento." : "From a favorite, press Mark as applied to start tracking it."}</p></div>}
    <div className="application-list">{visible.map((item) => <article className={`application-card status-${item.status}`} key={item.application_id}>
      <header><div><small className="application-status-badge">{labels[item.status]}</small><h3>{item.title}</h3><p>{item.company} · {item.location}</p></div><a href={item.apply_url} target="_blank" rel="noopener noreferrer">{es ? "Abrir publicación ↗" : "Open listing ↗"}</a></header>
      <div className="application-meta"><span>{es ? "Perfil" : "Profile"}: <strong>{profileName(item.profile_id)}</strong></span><span>{es ? "Inicio" : "Started"}: <strong>{new Date(item.created_at).toLocaleDateString(locale)}</strong></span></div>
      <div className="application-status-field"><FilterSelect icon="↗" label={es ? "Etapa actual" : "Current stage"} ariaLabel={es ? "Etapa de candidatura" : "Application stage"} disabled={busy === item.application_id} value={item.status} onChange={(value) => void update(item, { status: value as ApplicationStatus })} options={statusOrder.map((status) => ({ value: status, label: labels[status] }))} /></div>
      <label><span>{es ? "Notas privadas" : "Private notes"}</span><textarea defaultValue={item.notes} onBlur={(e) => { if (e.target.value !== item.notes) void update(item, { notes: e.target.value }); }} placeholder={es ? "Contacto, próxima fecha, observaciones…" : "Contact, next date, observations…"} /></label>
      <details><summary>{es ? "Ver historial" : "View history"}</summary><ol className="application-timeline">{item.events.slice().reverse().map((event) => <li key={event.event_id} data-status={event.status}><time>{new Date(event.created_at).toLocaleString(locale)}</time><strong>{labels[event.status]}</strong>{event.note && <span>{event.note}</span>}</li>)}</ol></details>
      <button type="button" className="application-delete" disabled={busy === item.application_id} onClick={async () => { if (!confirm(es ? "¿Eliminar este seguimiento? El favorito permanecerá guardado." : "Delete this tracking record? The favorite remains saved.")) return; setBusy(item.application_id); try { await api.deleteApplication(item.application_id); setItems((current) => current.filter((value) => value.application_id !== item.application_id)); } finally { setBusy(""); } }}>{es ? "Eliminar seguimiento" : "Delete tracking"}</button>
    </article>)}</div>
  </section>;
}
