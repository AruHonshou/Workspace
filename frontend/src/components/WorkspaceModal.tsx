import { useEffect, useRef, type ReactNode } from "react";

interface WorkspaceModalProps {
  title: string;
  eyebrow: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
  closeLabel?: string;
}

export function WorkspaceModal({ title, eyebrow, onClose, children, wide = false, closeLabel = "Cerrar panel" }: WorkspaceModalProps) {
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeButton.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="workspace-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className={`workspace-modal ${wide ? "is-wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby="workspace-modal-title">
        <header className="workspace-modal-header">
          <div className="window-lights" aria-hidden="true"><i /><i /><i /></div>
          <div className="window-title"><span>{eyebrow}</span><h2 id="workspace-modal-title">{title}</h2></div>
          <div className="window-mode" aria-hidden="true"><b>AME/OS</b><small>LOCAL · SECURE</small></div>
          <button ref={closeButton} type="button" className="modal-close" onClick={onClose} aria-label={closeLabel}>×</button>
        </header>
        <div className="workspace-modal-body">{children}</div>
      </section>
    </div>
  );
}
