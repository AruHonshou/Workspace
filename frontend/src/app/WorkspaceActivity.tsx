import { createContext, useContext } from "react";

// Cached pages stay mounted to preserve work, but only the visible page may
// claim focus, expose popovers or refresh its read-only list on activation.
export const WorkspaceActivity = createContext(true);

export function useWorkspaceActive(): boolean {
  return useContext(WorkspaceActivity);
}
