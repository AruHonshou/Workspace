import type { ViewId } from "../types";

export function WorkspaceIcon({ name }: { name: ViewId | "home" | "arrow" | "motion" | "lock" | "close" }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === "search" && <><circle cx="10.7" cy="10.7" r="6.7" /><path d="m16 16 4.5 4.5" /></>}
    {name === "favorites" && <path d="M20.6 5.6a5.2 5.2 0 0 0-7.4 0L12 6.8l-1.2-1.2a5.2 5.2 0 0 0-7.4 7.4L12 21l8.6-8a5.2 5.2 0 0 0 0-7.4Z" />}
    {name === "profile" && <path d="M14 3H5v18h14V8Z M14 3v5h5 M8 12h8 M8 16h6" />}
    {name === "about" && <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>}
    {name === "applications" && <><rect x="3" y="6" width="18" height="15" rx="2" /><path d="M8 6V3h8v3 M3 12h18 M10 12v3h4v-3" /></>}
    {name === "linkedin" && <><rect x="3" y="3" width="18" height="18" rx="3" /><path d="M7.5 10v7 M7.5 7v.1 M11.5 17v-7m0 3a3 3 0 0 1 6 0v4" /></>}
    {name === "settings" && <><path d="m10 3-.7 2.4-2 .9L5 5.7 3 9l1.8 1.8v2.4L3 15l2 3.3 2.3-.6 2 .9.7 2.4h4l.7-2.4 2-.9 2.3.6 2-3.3-1.8-1.8v-2.4L21 9l-2-3.3-2.3.6-2-.9L14 3Z" /><circle cx="12" cy="12" r="3" /></>}
    {name === "home" && <path d="m3 10 9-7 9 7 M5 9v12h14V9 M9 21v-7h6v7" />}
    {name === "arrow" && <path d="M5 12h14 M13 6l6 6-6 6" />}
    {name === "motion" && <><path d="M3 8h4 M2 12h5 M3 16h4" /><circle cx="15" cy="12" r="7" /><path d="m13 9 5 3-5 3Z" /></>}
    {name === "lock" && <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3 M12 15v2" /></>}
    {name === "close" && <path d="m6 6 12 12 M18 6 6 18" />}
  </svg>;
}
