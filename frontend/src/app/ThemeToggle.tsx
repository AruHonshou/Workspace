import type { Locale } from "../types";
import type { WorkspaceTheme } from "./useWorkspaceTheme";
export function ThemeToggle({ locale, theme, onClick }: { locale: Locale; theme: WorkspaceTheme; onClick: () => void }) {
  const label = locale === "es" ? (theme === "dark" ? "Activar modo claro" : "Activar modo oscuro") : (theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
  return <button type="button" className="workspace-theme-toggle" aria-label={label} title={label} aria-pressed={theme === "dark"} onClick={onClick}>
    <svg key={theme} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {theme === "dark" ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5" /></> : <path d="M20.6 13.3A8.7 8.7 0 0 1 10.7 3.4 8.7 8.7 0 1 0 20.6 13.3Z" />}
    </svg>
  </button>;
}
