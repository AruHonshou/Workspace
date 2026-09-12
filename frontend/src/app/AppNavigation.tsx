import { useEffect, useRef } from "react";
import { NavLink } from "react-router";
import type { Locale, ViewId } from "../types";
import { WorkspaceIcon } from "./WorkspaceIcon";

export const workspaceLinks: { path: string; view: ViewId; es: string; en: string }[] = [
  { path: "/buscar", view: "search", es: "Buscar empleos", en: "Find jobs" },
  { path: "/favoritos", view: "favorites", es: "Favoritos", en: "Favorites" },
  { path: "/mi-cv", view: "profile", es: "Mi CV", en: "My résumé" },
  { path: "/sobre-mi", view: "about", es: "Sobre mí", en: "About me" },
  { path: "/candidaturas", view: "applications", es: "Candidaturas", en: "Applications" },
  { path: "/linkedin", view: "linkedin", es: "LinkedIn", en: "LinkedIn" },
  { path: "/configuracion", view: "settings", es: "Configuración", en: "Settings" },
];

export function AppNavigation({ locale, variant = "dock", destinations = {}, activePanel }: {
  locale: Locale; variant?: "dock" | "tabs";
  destinations?: Partial<Record<ViewId, string>>; activePanel?: ViewId | null;
}) {
  const nav = useRef<HTMLElement>(null);
  useEffect(() => {
    if (variant === "tabs") nav.current?.querySelector('[aria-current="page"]')?.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "instant" });
  }, [activePanel, variant]);
  return <nav ref={nav} className={`workspace-navigation workspace-navigation--${variant}`} aria-label={locale === "es" ? "Navegación principal" : "Main navigation"}>
    {workspaceLinks.map(item => <NavLink key={item.path} to={destinations[item.view] ?? item.path}
      aria-label={item[locale]} aria-current={activePanel === item.view ? "page" : undefined}
      className={() => activePanel === item.view ? "workspace-nav-link active" : "workspace-nav-link"}>
      <span className="workspace-nav-icon"><WorkspaceIcon name={item.view} /></span>
      <span className="workspace-nav-label">{item[locale]}</span>
      {variant === "tabs" && <span className="workspace-tab-indicator" aria-hidden="true" />}
    </NavLink>)}
  </nav>;
}
