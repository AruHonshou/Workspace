import { useState, type ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation, type Location } from "react-router";
import { PageFrame } from "../pages/PageFrame";
import { SavedJobDetailPage } from "../pages/SavedJobDetailPage";
import { WorkspaceActivity } from "./WorkspaceActivity";
import type { Locale, ViewId } from "../types";

export const panelPath = (panel: ViewId): string => ({
  search: "/buscar", profile: "/mi-cv",
  favorites: "/favoritos",
  about: "/sobre-mi", applications: "/candidaturas",
  linkedin: "/linkedin", settings: "/configuracion",
}[panel]);

export function panelFromLocation(location: Pick<Location, "pathname" | "search">): ViewId | null {
  if (location.pathname === "/buscar") return "search";
  if (/^\/favoritos(?:\/[^/]+)?\/?$/.test(location.pathname)) return "favorites";
  if (location.pathname === "/mi-cv") return "profile";
  if (location.pathname === "/sobre-mi") return "about";
  if (location.pathname === "/candidaturas") return "applications";
  if (location.pathname === "/linkedin") return "linkedin";
  if (location.pathname === "/configuracion") return "settings";
  return null;
}

type Props = {
  locale: Locale;
  activePanel: ViewId | null;
  renderView: (view: ViewId) => ReactNode;
  home: ReactNode;
  workspaceVisible?: boolean;
};

export function WorkspaceRoutes(props: Props) {
  const { locale, renderView, home, workspaceVisible = true } = props;
  const location = useLocation();
  const isWorkspace = panelFromLocation(location) !== null;
  const [visited, setVisited] = useState<Location[]>(() => isWorkspace ? [location] : []);
  // Add the destination during render, so direct links never flash another
  // page. Keys are pathnames: browser history entries share the same draft.
  const prior = visited.find((entry) => entry.pathname === location.pathname);
  if (isWorkspace && prior !== location) {
    setVisited((current) => prior
      ? current.map((entry) => entry.pathname === location.pathname ? location : entry)
      : [...current, location]);
  }
  const es = locale === "es";
  return <>
    {visited.map((entry) => {
      const active = entry.pathname === location.pathname && workspaceVisible;
      return <WorkspaceActivity.Provider key={entry.pathname} value={active}>
        <div className="workspace-tab-page" data-workspace-path={entry.pathname}
          hidden={!active} inert={!active} aria-hidden={!active || undefined}
          style={{ display: active ? "contents" : "none" }}>
          {/* Freeze each page's router context: useParams/useLocation and
              relative links must not drift when a different tab is active. */}
          <Routes location={entry}>
    <Route path="/buscar" element={<PageFrame title={es ? "Buscar empleos" : "Find jobs"} locale={locale}>{renderView("search")}</PageFrame>} />
    <Route path="/favoritos" element={<PageFrame title={es ? "Favoritos" : "Favorites"} locale={locale}>{renderView("favorites")}</PageFrame>} />
    <Route path="/favoritos/:id" element={<PageFrame title={es ? "Detalle del favorito" : "Favorite details"} locale={locale}><SavedJobDetailPage locale={locale} /></PageFrame>} />
    <Route path="/mi-cv" element={<PageFrame title={es ? "Mi CV" : "My résumé"} locale={locale}>{renderView("profile")}</PageFrame>} />
    <Route path="/sobre-mi" element={<PageFrame title={es ? "Sobre mí" : "About me"} locale={locale}>{renderView("about")}</PageFrame>} />
    <Route path="/candidaturas" element={<PageFrame title={es ? "Candidaturas" : "Applications"} locale={locale}>{renderView("applications")}</PageFrame>} />
    <Route path="/linkedin" element={<PageFrame title="LinkedIn" locale={locale}>{renderView("linkedin")}</PageFrame>} />
    <Route path="/configuracion" element={<PageFrame title={es ? "Configuración" : "Settings"} locale={locale}>{renderView("settings")}</PageFrame>} />
          </Routes>
        </div>
      </WorkspaceActivity.Provider>;
    })}
    {!isWorkspace && <Routes>
    <Route path="/" element={home} />
    <Route path="/resultados" element={<Navigate to="/buscar" replace />} />
    <Route path="*" element={<PageFrame title={es ? "Página no encontrada" : "Page not found"} locale={locale}><Link to="/buscar">{es ? "Ir al buscador" : "Go to search"}</Link></PageFrame>} />
    </Routes>}
  </>;
}
