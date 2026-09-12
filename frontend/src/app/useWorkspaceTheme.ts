import { useLayoutEffect, useState } from "react";
export type WorkspaceTheme = "light" | "dark";
export const THEME_KEY = "workspace-theme";
function storedTheme(): WorkspaceTheme | null {
  try { const value = localStorage.getItem(THEME_KEY); return value === "light" || value === "dark" ? value : null; }
  catch { return null; }
}
function systemTheme(): WorkspaceTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
/** Theme is local and independent of profiles and API settings. */
export function useWorkspaceTheme() {
  const [preference, setPreference] = useState<WorkspaceTheme | null>(storedTheme);
  const [system, setSystem] = useState<WorkspaceTheme>(systemTheme);
  const theme = preference ?? system;
  useLayoutEffect(() => { document.documentElement.dataset.workspaceTheme = theme; }, [theme]);
  useLayoutEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const change = () => setSystem(media.matches ? "dark" : "light");
    const sync = (event: StorageEvent) => { if (event.key === THEME_KEY || event.key === null) setPreference(storedTheme()); };
    media.addEventListener("change", change);
    window.addEventListener("storage", sync);
    return () => { media.removeEventListener("change", change); window.removeEventListener("storage", sync); };
  }, []);
  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setPreference(next);
    try { localStorage.setItem(THEME_KEY, next); } catch { /* Keep working this session. */ }
  }
  return { theme, toggleTheme };
}
