import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useWorkspaceActive } from "../app/WorkspaceActivity";
import {
  api,
  type BackendProfile,
  type DeepFitAnalysisV2,
  type SavedJob,
} from "../api/client";
import { SafeRichText } from "../components/SafeRichText";
import { FilterSelect } from "../components/DashboardViews";
import type { ATSResumeVersion, InterviewGuide, Locale } from "../types";

const activeGuideStatuses = new Set(["preparing", "reviewing", "rendering"]);

function errorText(cause: unknown, es: boolean): string {
  const message = cause instanceof Error ? cause.message : String(cause);
  if (!es) return message;

  if (/DeepSeek could not complete the fit analysis/i.test(message)) {
    return "DeepSeek no pudo completar el análisis de brechas. Inténtalo nuevamente.";
  }
  if (/DeepSeek could not (complete|create|generate)/i.test(message)) {
    return "DeepSeek no pudo completar la operación. Inténtalo nuevamente.";
  }
  if (/temporarily unreachable/i.test(message)) {
    return "DeepSeek no respondió temporalmente. Inténtalo nuevamente.";
  }
  return message;
}

function guideStatusLabel(status: InterviewGuide["status"], es: boolean): string {
  const labels: Record<InterviewGuide["status"], [string, string]> = {
    preparing: ["Analizando requisitos", "Analyzing requirements"],
    reviewing: ["Revisando la guía", "Reviewing the guide"],
    rendering: ["Preparando el PDF", "Preparing the PDF"],
    ready: ["PDF listo", "PDF ready"],
    failed: ["Necesita reintento", "Retry needed"],
  };
  return labels[status]?.[es ? 0 : 1] ?? status;
}

function atsStatusLabel(status: ATSResumeVersion["status"], es: boolean): string {
  const labels: Partial<Record<ATSResumeVersion["status"], [string, string]>> = {
    preparing: ["Preparando el borrador", "Preparing the draft"],
    drafting: ["Redactando el borrador", "Drafting the résumé"],
    reviewing: ["Revisando afirmaciones", "Reviewing claims"],
    awaiting_approval: ["Listo para tu revisión", "Ready for your review"],
    rendering: ["Renderizando el PDF", "Rendering the PDF"],
    ready: ["PDF listo", "PDF ready"],
    failed: ["No se pudo crear", "Could not create"],
    approved: ["Aprobado", "Approved"],
  };
  return labels[status]?.[es ? 0 : 1] ?? status;
}

export function SavedJobDetailPage({ locale }: { locale: Locale }) {
  const es = locale === "es";
  const workspaceActive = useWorkspaceActive();
  const workspaceActiveRef = useRef(workspaceActive);
  workspaceActiveRef.current = workspaceActive;
  const navigate = useNavigate();
  const { id = "" } = useParams<{ id: string }>();
  const [job, setJob] = useState<SavedJob | null>(null);
  const [profiles, setProfiles] = useState<BackendProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [analysis, setAnalysis] = useState<DeepFitAnalysisV2 | null>(null);
  const [guide, setGuide] = useState<InterviewGuide | null>(null);
  const [ats, setAts] = useState<ATSResumeVersion | null>(null);
  const [busyAction, setBusyAction] = useState<"analysis" | "guide" | "ats" | "approve" | "application" | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!workspaceActive || !id) return;
    let active = true;
    void Promise.all([api.getSavedJob(id), api.listProfiles()]).then(([saved, available]) => {
      if (!active) return;
      setJob(saved);
      setProfiles(available);
      setSelectedProfile((current) => available.some((profile) => profile.profile_id === current && profile.confirmed)
        ? current : available.find((profile) => profile.confirmed)?.profile_id || "");
    }).catch((cause) => { if (active) { setJob(null); setError(errorText(cause, es)); } });
    return () => { active = false; };
  }, [id, workspaceActive]);

  useEffect(() => {
    if (!selectedProfile) return;
    let active = true;
    void api.getSavedJobGuide(id, selectedProfile).then((storedGuide) => {
      if (active) setGuide(storedGuide);
    }).catch(() => {
      if (active) setGuide(null);
    });
    void api.getSavedJobResumes(id, selectedProfile).then((versions) => {
      if (active) setAts(versions[0] ?? null);
    }).catch(() => { if (active) setAts(null); });
    return () => { active = false; };
  }, [id, selectedProfile]);

  // Guides are generated in the background. Poll only while a real operation is active;
  // this keeps the page responsive without creating duplicate billable requests.
  useEffect(() => {
    if (!guide || !activeGuideStatuses.has(guide.status)) return;
    let active = true;
    const timer = window.setInterval(() => {
      void api.getSavedJobGuide(id, selectedProfile).then((updated) => {
        if (active) setGuide(updated);
      }).catch(() => undefined);
    }, 1600);
    return () => { active = false; window.clearInterval(timer); };
  }, [guide?.guide_id, guide?.status, id, selectedProfile]);

  const confirmedProfiles = useMemo(() => profiles.filter((profile) => profile.confirmed), [profiles]);
  const selected = profiles.find((profile) => profile.profile_id === selectedProfile);

  function changeProfile(profileId: string) {
    setSelectedProfile(profileId);
    // Analyses and documents are revision/profile specific. Do not leave a
    // previous profile's result on screen after the user switches profiles.
    setAnalysis(null);
    setGuide(null);
    setAts(null);
    setError("");
  }

  async function analyze() {
    if (!job || !selected?.confirmed || busyAction) return;
    setBusyAction("analysis"); setError("");
    try { setAnalysis(await api.analyzeSavedJob(id, selected.profile_id, locale)); }
    catch (cause) { setError(errorText(cause, es)); }
    finally { setBusyAction(null); }
  }

  async function prepareGuide() {
    if (!job || !selected?.confirmed || busyAction) return;
    setBusyAction("guide"); setError("");
    try {
      const updated = guide
        ? await api.regenerateSavedJobGuide(id, selected.profile_id)
        : await api.prepareSavedJobGuide(id, selected.profile_id);
      setGuide(updated);
    } catch (cause) { setError(errorText(cause, es)); }
    finally { setBusyAction(null); }
  }

  async function createAtsResume() {
    if (!job || !selected?.confirmed || busyAction) return;
    setBusyAction("ats"); setError("");
    try {
      setAts(await api.prepareSavedJobResume(id, selected.profile_id, Boolean(ats)));
    } catch (cause) { setError(errorText(cause, es)); }
    finally { setBusyAction(null); }
  }

  async function approveAtsResume() {
    if (!ats || ats.status !== "awaiting_approval" || busyAction) return;
    setBusyAction("approve"); setError("");
    try { setAts(await api.approveATSResume(ats.version_id || ats.resume_id)); }
    catch (cause) { setError(errorText(cause, es)); }
    finally { setBusyAction(null); }
  }

  if (error && !job) return <p role="alert">{error}</p>;
  if (!job) return <p role="status">{es ? "Cargando vacante…" : "Loading saved job…"}</p>;

  const guideActive = Boolean(guide && activeGuideStatuses.has(guide.status));
  const canGenerate = Boolean(selected?.confirmed) && !busyAction;
  const atsSections = ats?.document ? [
    { key: "experience", label: es ? "Experiencia relevante" : "Relevant experience", lines: ats.document.experience },
    { key: "projects", label: es ? "Proyectos relevantes" : "Relevant projects", lines: ats.document.projects },
    { key: "education", label: es ? "Educación" : "Education", lines: ats.document.education },
    { key: "certifications", label: es ? "Certificaciones" : "Certifications", lines: ats.document.certifications },
    { key: "languages", label: es ? "Idiomas" : "Languages", lines: ats.document.languages ?? [] },
  ].filter((section) => section.lines.length > 0) : [];
  return <article className="saved-job-detail">
    <Link className="page-back-link" to="/favoritos">{es ? "← Todos los favoritos" : "← All favorites"}</Link>
    <header>
      <span>{job.source_portals?.join(" · ") || "Portal"}</span>
      <h2>{job.title}</h2>
      <p>{job.company} · {job.location || (es ? "Ubicación no indicada" : "Location not specified")}</p>
      {job.published_at && <small>{es ? "Publicado" : "Published"}: {new Date(job.published_at).toLocaleString(locale)}</small>}
    </header>
    <section className="saved-job-workbench">
      <div className="saved-job-detail-actions">
        <a href={job.apply_url} target="_blank" rel="noopener noreferrer">{job.apply_url_type === "portal" ? (es ? "Abrir portal ↗" : "Open portal ↗") : (es ? "Abrir publicación ↗" : "Open listing ↗")}</a>
        <label>{es ? "Perfil para documentos" : "Profile for documents"}
          <FilterSelect icon="▣" label={es ? "PERFIL" : "PROFILE"}
            ariaLabel={es ? "Perfil para documentos" : "Profile for documents"}
            value={selectedProfile} onChange={changeProfile}
            disabled={!confirmedProfiles.length || Boolean(busyAction)}
            options={[{value: "", label: es ? "Selecciona un perfil" : "Select a profile"},
              ...confirmedProfiles.map((profile) => ({value: profile.profile_id, label: profile.display_name || profile.name, glyph: "✓"}))]} />
        </label>
        <button type="button" onClick={() => void analyze()} disabled={!canGenerate}>{busyAction === "analysis" ? (es ? "Analizando…" : "Analyzing…") : (es ? "Analizar brechas" : "Analyze gaps")}</button>
        <button type="button" onClick={() => void prepareGuide()} disabled={!canGenerate || guideActive}>{busyAction === "guide" ? (es ? "Preparando…" : "Preparing…") : guide?.status === "ready" ? (es ? "Regenerar guía" : "Regenerate guide") : guide?.status === "failed" ? (es ? "Reintentar guía" : "Retry guide") : (es ? "Preparar entrevista" : "Prepare interview")}</button>
        <button type="button" className="saved-job-ats-button" onClick={() => void createAtsResume()} disabled={!canGenerate}>{busyAction === "ats" ? (es ? "Creando CV…" : "Creating résumé…") : ats ? (es ? "Volver a crear CV ATS" : "Recreate ATS résumé") : (es ? "Crear CV ATS" : "Create ATS résumé")}</button>
        <button type="button" className="saved-job-application-button" onClick={async () => { if (!selected?.confirmed || busyAction) return; setBusyAction("application"); setError(""); try { await api.createApplication(id, selected.profile_id); if (workspaceActiveRef.current) navigate("/candidaturas"); } catch (cause) { setError(errorText(cause, es)); } finally { setBusyAction(null); } }} disabled={!canGenerate}>{busyAction === "application" ? (es ? "Guardando…" : "Saving…") : (es ? "Marcar como postulado" : "Mark as applied")}</button>
      </div>
      {!confirmedProfiles.length && <p className="saved-job-inline-warning" role="status">{es ? "Confirma un perfil en Mi CV antes de pedir análisis o documentos." : "Confirm a profile in My résumé before requesting analysis or documents."}</p>}
      {error && <p className="saved-job-inline-error" role="alert">{error}</p>}
    </section>
    <section><h3>{es ? "Descripción" : "Description"}</h3><SafeRichText value={job.description} /></section>
    {analysis && <section className="saved-job-analysis"><h3>{es ? "Encaje estimado" : "Estimated fit"}: {Math.round(analysis.score)}%</h3><p>{analysis.executive_summary}</p><h4>{es ? "Requisitos frente a evidencia" : "Requirements against evidence"}</h4><div className="saved-job-requirements">{(analysis.requirement_analysis ?? []).map((item) => <article className={`status-${item.status}`} key={item.requirement}><span>{item.status === "supported" ? "✓" : item.status === "gap" ? "!" : "?"}</span><div><small>{item.priority} · {item.category}</small><strong>{item.requirement}</strong>{item.explanation && <p>{item.explanation}</p>}{(item.evidence ?? []).length > 0 && <ul>{(item.evidence ?? []).map((evidence) => <li key={evidence}>{evidence}</li>)}</ul>}</div></article>)}</div><h4>{es ? "Brechas prioritarias" : "Priority gaps"}</h4><ul>{(analysis.priority_gaps || []).map((gap) => <li key={gap}>{gap}</li>)}</ul><h4>{es ? "Acciones para tu CV" : "CV actions"}</h4><ul>{(analysis.cv_actions || []).map((action) => <li key={action}>{action}</li>)}</ul>{analysis.integrity_notice && <small className="saved-job-integrity-note">{analysis.integrity_notice}</small>}</section>}
    {guide && <section className={`saved-job-document saved-job-guide status-${guide.status}`}><div><h3>{es ? "Guía de entrevista" : "Interview guide"}</h3><strong>{guideStatusLabel(guide.status, es)}</strong></div><p>{guide.status === "failed" ? (guide.error ? errorText(new Error(guide.error), es) : (es ? "La guía no se pudo completar." : "The guide could not be completed.")) : guide.status === "ready" ? (es ? "La guía fue revisada y está lista para abrirse." : "The guide was reviewed and is ready to open.") : (es ? "La guía se prepara en segundo plano con el perfil seleccionado." : "The guide is prepared in the background using the selected profile.")}</p>{guide.document_id && selected && <div className="saved-job-document-links"><a href={api.savedJobGuideUrl(id, selected.profile_id, "inline")} target="_blank" rel="noopener noreferrer">{es ? "Abrir guía PDF ↗" : "Open interview PDF ↗"}</a><a href={api.savedJobGuideUrl(id, selected.profile_id, "attachment")}>{es ? "Descargar PDF ↓" : "Download PDF ↓"}</a></div>}</section>}
    {ats && <section className={`saved-job-document saved-job-ats status-${ats.status}`}>
      <div><h3>{es ? "CV ATS para revisión" : "ATS résumé for review"}</h3><strong>{atsStatusLabel(ats.status, es)}</strong></div>
      {ats.error && <p className="saved-job-inline-error">{errorText(new Error(ats.error), es)}</p>}
      {ats.document && <>
        <div className="saved-job-ats-preview">
          <header><small>{es ? "BORRADOR ATS" : "ATS DRAFT"}</small><h4>{ats.document.headline}</h4><p>{ats.document.professional_summary}</p></header>
          {ats.document.skills.length > 0 && <section><h5>{es ? "Habilidades clave" : "Core skills"}</h5><div className="saved-job-skill-list">{ats.document.skills.slice(0, 24).map((skill) => <span key={skill}>{skill}</span>)}</div></section>}
          {atsSections.map((section) => <section key={section.key}><h5>{section.label}</h5><ul>{section.lines.map((line, index) => <li key={`${section.key}-${index}-${line.proposed_text}`}>{line.context_heading && <strong className="ats-context-heading">{line.context_heading}</strong>}{line.proposed_text}</li>)}</ul></section>)}
        </div>
        <details className="saved-job-ats-trace"><summary>{es ? "Comprobar el origen de cada afirmación" : "Verify the source of every claim"}</summary><p>{es ? "Esta comparación es sólo para revisión; no aparece en el PDF final." : "This comparison is only for review and is not included in the final PDF."}</p>{atsSections.flatMap((section) => section.lines).map((line, index) => <div className="saved-job-ats-line" key={`${index}-${line.proposed_text}`}><small>{es ? "Evidencia original" : "Original evidence"}</small><p>{line.original_text}</p><small>{es ? "Redacción propuesta" : "Proposed wording"}</small><strong>{line.proposed_text}</strong></div>)}</details>
        {ats.review_issues?.length ? <ul className="saved-job-review-issues">{ats.review_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : null}
      </>}
      {ats.status === "awaiting_approval" && <button type="button" className="saved-job-approve" onClick={() => void approveAtsResume()} disabled={busyAction === "approve"}>{busyAction === "approve" ? (es ? "Generando PDF…" : "Creating PDF…") : (es ? "Aprobar y crear PDF" : "Approve and create PDF")}</button>}
      {ats.status === "ready" && <a className="saved-job-download" href={api.atsResumeUrl(ats.resume_id, "pdf")} target="_blank" rel="noopener noreferrer">{es ? "Abrir o descargar CV ATS PDF ↗" : "Open or download ATS résumé PDF ↗"}</a>}
    </section>}
    <aside className="saved-job-next-step"><strong>{es ? "Control de evidencia" : "Evidence control"}</strong><p>{es ? "El análisis y los documentos usan sólo hechos confirmados del perfil elegido. Revisa el borrador ATS antes de aprobarlo; la vacante guardada no queda ligada permanentemente a un perfil." : "Analysis and documents use only confirmed facts from the selected profile. Review the ATS draft before approval; the saved job is not permanently tied to a profile."}</p></aside>
  </article>;
}
