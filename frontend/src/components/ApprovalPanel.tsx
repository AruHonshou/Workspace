import { useEffect, useMemo, useState } from "react";
import type { Translate } from "../i18n";
import type { ApprovalArtifact, ApprovalRequest, JobRecord } from "../types";

interface ApprovalPanelProps {
  approval: ApprovalRequest;
  jobs: JobRecord[];
  artifacts: ApprovalArtifact[];
  t: Translate;
  onDecision: (decision: string, entityIds: string[]) => Promise<void>;
}

export function ApprovalPanel({ approval, jobs, artifacts, t, onDecision }: ApprovalPanelProps) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>(approval.entity_ids.slice(0, 3));
  const shortlistJobs = useMemo(
    () => approval.entity_ids.map((id) => jobs.find((job) => job.id === id)).filter(Boolean) as JobRecord[],
    [approval.entity_ids, jobs],
  );
  const reviewDataReady = approval.kind === "shortlist_selection"
    ? shortlistJobs.length === approval.entity_ids.length
    : approval.kind === "application_approval"
      ? artifacts.length === approval.entity_ids.length
      : true;

  useEffect(() => {
    setSelectedIds(approval.entity_ids.slice(0, 3));
  }, [approval.approval_id, approval.entity_ids]);

  function toggleJob(jobId: string): void {
    setSelectedIds((current) => current.includes(jobId)
      ? current.filter((id) => id !== jobId)
      : current.length < 3 ? [...current, jobId] : current);
  }

  async function decide(decision: string): Promise<void> {
    setBusy(decision);
    setError(null);
    try {
      const selectable = approval.kind === "shortlist_selection" || approval.kind === "application_approval";
      const entityIds = selectable ? selectedIds : approval.entity_ids;
      if ((decision === "select" || decision === "approve") && selectable && entityIds.length === 0) {
        throw new Error(t("approval.shortlistRequired"));
      }
      await onDecision(decision, entityIds);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <aside className="approval-panel" aria-labelledby="approval-title" aria-live="assertive">
      <div className="approval-icon" aria-hidden="true">!</div>
      <div className="approval-copy">
        <span className="eyebrow">Human-in-the-loop</span>
        <h2 id="approval-title">{t("approval.title")}</h2>
        <strong>{t(`approval.${approval.kind}`)}</strong>
        <p>{approval.summary || t("approval.pending")}</p>
        {!reviewDataReady && <p role="status">{t("approval.loadingEvidence")}</p>}
        {approval.kind === "shortlist_selection" && (
          <fieldset className="shortlist-picker">
            <legend>{t("approval.shortlistLegend")}</legend>
            {(shortlistJobs.length ? shortlistJobs : approval.entity_ids.map((id) => ({ id, title: id, company: "", fitScore: 0 } as JobRecord))).map((job) => {
              const checked = selectedIds.includes(job.id);
              return (
                <label key={job.id}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={!checked && selectedIds.length >= 3}
                    onChange={() => toggleJob(job.id)}
                  />
                  <span><strong>{job.title}</strong><small>{job.company}{job.fitScore ? ` · ${job.fitScore}%` : ""}</small></span>
                </label>
              );
            })}
            <small>{t("approval.shortlistCount", { count: selectedIds.length })}</small>
          </fieldset>
        )}
        {approval.kind === "application_approval" && (
          <fieldset className="application-review-list">
            <legend>{t("approval.reviewLegend")}</legend>
            {artifacts.map((artifact) => {
              const checked = selectedIds.includes(artifact.id);
              return (
                <div key={artifact.id}>
                  <label>
                    <input type="checkbox" checked={checked} onChange={() => toggleJob(artifact.id)} />
                    <span>{artifact.title} · v{artifact.version}</span>
                  </label>
                  <details>
                    <summary>{t("approval.reviewOpen")}</summary>
                    <p>{artifact.content}</p>
                    <ul>{artifact.claims.map((claim) => <li key={`${artifact.id}-${claim.text}`}>{claim.text}</li>)}</ul>
                  </details>
                </div>
              );
            })}
            <small>{t("approval.reviewCount", { count: selectedIds.length })}</small>
          </fieldset>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="approval-actions">
        {approval.allowed_decisions.map((decision) => (
          <button
            key={decision}
            type="button"
            className={decision === "approve" || decision === "select" ? "primary-button" : "secondary-button"}
            disabled={busy !== null || ((decision === "approve" || decision === "select") && !reviewDataReady)}
            onClick={() => void decide(decision)}
          >
            {busy === decision ? "…" : t(`approval.${decision}`)}
          </button>
        ))}
      </div>
    </aside>
  );
}
