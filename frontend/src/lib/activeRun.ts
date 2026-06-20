// Single home for the single-active-run frontend convention (Software Lock §5.1/§6.7).
// The active analysis id is whatever the browser has cached; there is no server-side per-client lock.
const KEY = "hf-active-run";

export function getActiveRunId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setActiveRunId(id: string): void {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* storage unavailable; resume simply won't persist */
  }
}

export function clearActiveRunId(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
