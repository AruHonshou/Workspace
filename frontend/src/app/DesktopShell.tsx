import { Component, lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type PointerEvent } from "react";
import { Link, useLocation } from "react-router";
import type { Locale, ViewId } from "../types";
import { AppNavigation, workspaceLinks } from "./AppNavigation";
import { WorkspaceRoutes, panelFromLocation } from "./WorkspaceRoutes";
import { WorkspaceIcon } from "./WorkspaceIcon";
import { useDeskTransition, useReducedMotion } from "./useDeskTransition";
import { clampDeskLook, type DeskLook } from "../components/deskSceneCamera";
import { DESK_IDENTITY } from "../data/deskIdentity";

const DeskScene = lazy(() => import("../components/DeskScene").then(module => ({ default: module.DeskScene })));

class GraphicsBoundary extends Component<{ children: ReactNode; onUnavailable: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onUnavailable(); }
  render() {
    return this.state.failed
      ? <img className="desk-scene-fallback" src="/branding/desk-fallback.svg" alt="" />
      : this.props.children;
  }
}

export function DesktopShell({ locale, onLocaleChange, renderView, notice, onDismissNotice }: {
  locale: Locale; onLocaleChange: () => void; renderView: (view: ViewId) => ReactNode;
  notice: string | null; onDismissNotice: () => void;
}) {
  const location = useLocation();
  const es = locale === "es";
  const atHome = location.pathname === "/";
  const activePanel = panelFromLocation(location);
  const reducedMotion = useReducedMotion();
  const [staticView, setStaticView] = useState(() => localStorage.getItem("workspace-static-view") === "true");
  const [unavailable, setUnavailable] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const { phase, settle } = useDeskTransition(atHome, reducedMotion || staticView || unavailable);
  const lastPaths = useRef<Partial<Record<ViewId, string>>>({});
  const homeHeading = useRef<HTMLHeadingElement>(null);
  const screenElement = useRef<HTMLElement>(null);
  const stageElement = useRef<HTMLDivElement>(null);
  const linkedinHotspot = useRef<HTMLAnchorElement>(null);
  const githubHotspot = useRef<HTMLAnchorElement>(null);
  const portfolioHotspot = useRef<HTMLAnchorElement>(null);
  const look = useRef<DeskLook>({ yaw: 0, pitch: 0 });
  const requestFrame = useRef<(() => void) | null>(null);
  const drag = useRef<{ id: number; x: number; y: number; look: DeskLook } | null>(null);
  const hadWorkspace = useRef(!atHome);
  if (activePanel) lastPaths.current[activePanel] = location.pathname + location.search;
  const working = phase === "working";
  const homeVisible = phase === "home";
  const moving = phase === "entering" || phase === "leaving";
  const activeLabel = workspaceLinks.find(item => item.view === activePanel)?.[locale] ?? (es ? "Página" : "Page");
  const onUnavailable = useCallback(() => { setUnavailable(true); setSceneReady(false); }, []);
  const onSceneReady = useCallback(() => setSceneReady(true), []);

  useEffect(() => { if (working) look.current = { yaw: 0, pitch: 0 }; }, [working]);
  useLayoutEffect(() => {
    if (sceneReady || !stageElement.current || !screenElement.current) return;
    const position = () => {
      const stage = stageElement.current!, screen = screenElement.current!;
      const width = stage.clientWidth, height = stage.clientHeight;
      const scale = Math.max(width / 1600, height / 1000), pixels = width < 600 ? 420 : 1000;
      screen.style.width = `${pixels}px`;
      screen.style.height = `${pixels * 385 / 920}px`;
      screen.style.transform = `translate(${(width - 1600 * scale) / 2 + 340 * scale}px, ${(height - 1000 * scale) / 2 + 220 * scale}px) scale(${920 * scale / pixels})`;
      screen.dataset.compact = String(width < 600);
    };
    position();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(position);
    observer.observe(stageElement.current);
    return () => observer.disconnect();
  }, [sceneReady]);

  function boundedLook(next: DeskLook) {
    const stage = stageElement.current;
    return clampDeskLook(next, stage?.clientHeight ? stage.clientWidth / stage.clientHeight : undefined);
  }
  function changeLook(yaw: number, pitch = 0) {
    look.current = boundedLook({ yaw: look.current.yaw + yaw, pitch: look.current.pitch + pitch });
    requestFrame.current?.();
  }
  function resetLook() { look.current = { yaw: 0, pitch: 0 }; requestFrame.current?.(); }
  function startLook(event: PointerEvent<HTMLDivElement>) {
    if (!homeVisible || unavailable || event.button !== 0 || event.defaultPrevented) return;
    if ((event.target as HTMLElement).closest("button, a, input, textarea, select, [contenteditable=true]")) return;
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, look: { ...look.current } };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  function moveLook(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current;
    if (!start || start.id !== event.pointerId || !homeVisible) return;
    look.current = boundedLook({ yaw: start.look.yaw - (event.clientX - start.x) * .0018, pitch: start.look.pitch + (event.clientY - start.y) * .0013 });
    requestFrame.current?.();
  }
  function stopLook(event: PointerEvent<HTMLDivElement>) {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  useEffect(() => {
    if (!homeVisible) { hadWorkspace.current = true; return; }
    document.title = es ? "Workspace · Tu espacio profesional" : "Workspace · Your career space";
    if (hadWorkspace.current) homeHeading.current?.focus({ preventScroll: true });
  }, [homeVisible, es]);

  function toggleStaticView() {
    setStaticView(current => {
      localStorage.setItem("workspace-static-view", String(!current));
      return !current;
    });
  }

  return <div className={`desktop-shell pov-shell phase-${phase} ${sceneReady ? "pov-ready" : "pov-fallback"}`} data-phase={phase}>
    <a className="skip-link" href={working ? "#main-content" : "#desktop-home"}>{es ? "Saltar al contenido" : "Skip to content"}</a>
    <div ref={stageElement} className="desktop-stage" aria-hidden={!homeVisible} inert={!homeVisible}
      tabIndex={homeVisible && !unavailable ? 0 : -1} role="region" aria-label={es ? "Mover la vista del escritorio" : "Look around the desk"}
      onPointerDown={startLook} onPointerMove={moveLook} onPointerUp={stopLook} onPointerCancel={stopLook} onLostPointerCapture={() => { drag.current = null; }}
      onKeyDown={event => {
        if (event.target !== event.currentTarget || !homeVisible) return;
        const direction = { ArrowLeft: [-.07, 0], ArrowRight: [.07, 0], ArrowUp: [0, .045], ArrowDown: [0, -.045] }[event.key];
        if (direction) { event.preventDefault(); changeLook(direction[0], direction[1]); }
        else if (event.key === "Home" || event.key === "Escape") { event.preventDefault(); resetLook(); }
      }}>
      <GraphicsBoundary onUnavailable={onUnavailable}><Suspense fallback={<div className="desk-scene-fallback"><img src="/branding/desk-fallback.svg" alt="" /></div>}>
        <DeskScene phase={phase} reducedMotion={reducedMotion || staticView} locale={locale} onSettled={settle} onUnavailable={onUnavailable}
          onReady={onSceneReady} screenElement={screenElement} look={look} requestFrame={requestFrame} hotspots={{ linkedin: linkedinHotspot, github: githubHotspot, portfolio: portfolioHotspot }} />
      </Suspense></GraphicsBoundary>
    </div>

    <div className="desktop-home-layer" inert={!homeVisible} aria-hidden={!homeVisible}>
      <header className="desktop-header">
        <Link to="/" className="workspace-brand" aria-label={es ? "Workspace, inicio" : "Workspace, home"}>
          <img src="/branding/workspace-mark.svg" width="34" height="34" alt="" />
          <span>Workspace<small>{es ? "TU ESPACIO PROFESIONAL" : "YOUR CAREER SPACE"}</small></span>
        </Link>
        <div className="desktop-header-tools">
          <button type="button" className="desktop-motion" aria-label={es ? "Animaciones de cámara" : "Camera animations"} aria-pressed={!staticView && !reducedMotion} onClick={toggleStaticView}
            title={es ? "Activar o desactivar las transiciones de cámara" : "Enable or disable camera transitions"}>
            <WorkspaceIcon name="motion" /><span>{es ? (staticView || reducedMotion ? "Sin animaciones" : "Animaciones") : (staticView || reducedMotion ? "Motion off" : "Motion on")}</span>
          </button>
          <button type="button" className="workspace-language" onClick={onLocaleChange} aria-label={es ? "Cambiar a inglés" : "Switch to Spanish"}>{es ? "EN" : "ES"}</button>
        </div>
      </header>
      <main ref={screenElement} className="desktop-home-copy monitor-home" id="desktop-home">
        <div className="monitor-home-top"><span>WORKSPACE</span><span><i />{es ? "TU ESPACIO PERSONAL" : "YOUR PERSONAL SPACE"}</span></div>
        <div className="monitor-home-content">
        <span className="desktop-eyebrow"><i />{es ? "UN NUEVO CAPÍTULO" : "YOUR NEXT CHAPTER"}</span>
        <h1 ref={homeHeading} tabIndex={-1}>{es ? <>Un espacio para<br /><em>lo que sigue.</em></> : <>A space for<br /><em>what comes next.</em></>}</h1>
        <p>{es ? "Descubre oportunidades, da forma a tu perfil y prepara tu próximo paso. A tu ritmo, en un solo lugar." : "Discover opportunities, shape your profile and prepare your next step. At your pace, in one place."}</p>
        <Link className="desktop-primary" to={lastPaths.current.search ?? "/buscar"}>{es ? "Explorar oportunidades" : "Explore opportunities"}<WorkspaceIcon name="arrow" /></Link>
        </div>
        <span className="desktop-home-note">{es ? "Tu escritorio. Tus posibilidades." : "Your desk. Your possibilities."}</span>
      </main>
      <div className="desk-object-links">
        <a ref={portfolioHotspot} className="desk-object-link desk-object-link--notebook" href={DESK_IDENTITY.portfolio} target="_blank" rel="noopener noreferrer" aria-label={es ? "Cuaderno: abrir portfolio de AruHonshou" : "Notebook: open AruHonshou’s portfolio"}>
          <span className="desk-object-dot">↗</span><span className="desk-object-tooltip"><strong>Portfolio</strong><span>{es ? "Conoce mi trabajo" : "Discover my work"} ↗</span></span>
        </a>
        <a ref={linkedinHotspot} className="desk-object-link desk-object-link--coffee" href={DESK_IDENTITY.linkedin} target="_blank" rel="noopener noreferrer" aria-label={es ? "Taza de café: abrir LinkedIn de Kendall Valverde" : "Coffee cup: open Kendall Valverde’s LinkedIn"}>
          <span className="desk-object-dot">in</span><span className="desk-object-tooltip"><strong>Kendall Valverde</strong><span>{es ? "Conversemos en LinkedIn" : "Let’s connect on LinkedIn"} ↗</span></span>
        </a>
        <a ref={githubHotspot} className="desk-object-link desk-object-link--mouse" href={DESK_IDENTITY.github} target="_blank" rel="noopener noreferrer" aria-label={es ? "Ratón: abrir GitHub de AruHonshou" : "Mouse: open AruHonshou’s GitHub"}>
          <span className="desk-object-dot">⌘</span><span className="desk-object-tooltip"><strong>AruHonshou</strong><span>{es ? "Explora mis proyectos en GitHub" : "Explore my projects on GitHub"} ↗</span></span>
        </a>
      </div>
      <div className="desk-look-controls" role="group" aria-label={es ? "Controles de la vista" : "View controls"}>
        <button type="button" disabled={!sceneReady} onClick={() => changeLook(-.15)} aria-label={es ? "Mirar a la izquierda" : "Look left"}>←</button>
        <button type="button" disabled={!sceneReady} onClick={resetLook} aria-label={es ? "Centrar vista" : "Center view"}>◎</button>
        <button type="button" disabled={!sceneReady} onClick={() => changeLook(.15)} aria-label={es ? "Mirar a la derecha" : "Look right"}>→</button>
      </div>
      <span className="desktop-corner-note"><WorkspaceIcon name="lock" />{es ? "Espacio de trabajo local" : "Local workspace"}</span>
    </div>

    <div className="browser-workspace" inert={!working} aria-hidden={!working}>
      <header className="browser-chrome">
        <div className="browser-tab-row">
          <Link to="/" className="browser-home" title={es ? "Volver al escritorio" : "Back to desk"} aria-label={es ? "Inicio" : "Home"}><WorkspaceIcon name="home" /></Link>
          <AppNavigation locale={locale} variant="tabs" destinations={lastPaths.current} activePanel={activePanel} />
          <button type="button" className="workspace-language" onClick={onLocaleChange} aria-label={es ? "Cambiar a inglés" : "Switch to Spanish"}>{es ? "EN" : "ES"}</button>
        </div>
        <div className="browser-location-row">
          <span className="browser-mini-mark"><img src="/branding/workspace-mark.svg" width="18" height="18" alt="" />Workspace</span>
          <div className="browser-location" aria-label={es ? "Ubicación actual" : "Current location"}><WorkspaceIcon name="lock" /><span>workspace</span><span className="browser-location-separator">/</span><strong>{activeLabel}</strong></div>
          <span className="browser-local-status"><i />{es ? "Aplicación local" : "Local application"}</span>
        </div>
      </header>
      <WorkspaceRoutes locale={locale} activePanel={activePanel} renderView={renderView} home={null} workspaceVisible={working} />
    </div>

    {moving && <div className="desktop-transition-status" role="status"><span>{es ? (phase === "entering" ? "Abriendo tu espacio…" : "Volviendo al escritorio…") : (phase === "entering" ? "Opening your workspace…" : "Returning to the desk…")}</span><button type="button" onClick={settle}>{es ? "Omitir animación" : "Skip animation"}</button></div>}
    {notice && <div className="app-toast" role="status" aria-live="polite"><span className="app-toast-signal" aria-hidden="true">✓</span><span className="app-toast-copy"><strong>{es ? "ACTUALIZACIÓN" : "UPDATE"}</strong>{notice}</span><button type="button" aria-label={es ? "Cerrar notificación" : "Close notification"} onClick={onDismissNotice}>×</button><span className="app-toast-timer" aria-hidden="true" /></div>}
  </div>;
}
