import { useId, useLayoutEffect, useRef, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useWorkspaceActive } from "../app/WorkspaceActivity";
import type { Locale } from "../types";
import { EditorialQuote } from "../components/EditorialQuote";

export function PageFrame({ title, locale, children }: { title: string; locale: Locale; children: ReactNode }) {
  const heading = useRef<HTMLHeadingElement>(null);
  const main = useRef<HTMLElement>(null);
  const scroll = useRef({ left: 0, top: 0 });
  const pageId = useId();
  const active = useWorkspaceActive();
  const location = useLocation();
  useLayoutEffect(() => {
    if (!active) return;
    document.title = `${title} · Workspace`;
    if (main.current) {
      main.current.scrollTop = scroll.current.top;
      main.current.scrollLeft = scroll.current.left;
    }
    heading.current?.focus({ preventScroll: true });
  }, [active, title, location.pathname]);
  return <main ref={main} id={active ? "main-content" : `workspace-page-${pageId}`}
    className="workspace-page" aria-labelledby={`page-title-${pageId}`}
    onScroll={(event) => { if (active) scroll.current = { top: event.currentTarget.scrollTop, left: event.currentTarget.scrollLeft }; }}>
    <div className="workspace-page-inner">
      <header className="page-titlebar">
        <Link to="/">{locale === "es" ? "← Inicio" : "← Home"}</Link>
        <div><span>WORKSPACE</span><h1 tabIndex={-1} ref={heading} id={`page-title-${pageId}`}>{title}</h1></div>
        <EditorialQuote path={location.pathname} locale={locale} />
      </header>
      <div className="page-content">{children}</div>
    </div>
  </main>;
}
