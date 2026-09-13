// Compatibility only: move existing preferences without touching professional data.
const previousKeys = [
  ["career-orchestrator-profile-id", "workspace-profile-id"],
  ["amework-search-country", "workspace-search-country"],
  ["amework-simple-search", "workspace-last-search-id"],
] as const;

export function migrateBrowserPreferences(storage?: Storage): void {
  for (const [previousKey, currentKey] of previousKeys) {
    try {
      const target = storage ?? window.localStorage;
      const previous = target.getItem(previousKey);
      if (previous === null) continue;
      if (target.getItem(currentKey) === null) target.setItem(currentKey, previous);
      // Keep the original if a storage implementation failed to persist the copy.
      if (target.getItem(currentKey) !== null) target.removeItem(previousKey);
    } catch {
      // Blocked storage must not prevent startup; an untransferred key stays intact.
    }
  }
}
