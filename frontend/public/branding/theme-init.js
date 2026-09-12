// Visual preference only: applied before the first paint.
try {
  const saved = localStorage.getItem("workspace-theme");
  document.documentElement.dataset.workspaceTheme = saved === "dark" || saved === "light"
    ? saved : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
} catch { document.documentElement.dataset.workspaceTheme = "light"; }
