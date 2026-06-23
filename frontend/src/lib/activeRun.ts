// Single home for the single-active-run frontend convention (Software Lock §5.1/§6.7).
// The active analysis id is whatever the browser has cached; there is no server-side per-client lock.
const KEY = "hf-active-run";

// A run id is only usable if it is a non-empty, non-sentinel string. The platform
// coerces localStorage.setItem(KEY, null/undefined) to the literal strings
// "null"/"undefined"; persisting one would route to /analysis/null and make the
// status poll 422 forever. Reject those everywhere.
function isUsableId(id: string | null | undefined): id is string {
  return !!id && id !== "null" && id !== "undefined";
}

export function getActiveRunId(): string | null {
  try {
    const id = localStorage.getItem(KEY);
    if (!isUsableId(id)) {
      if (id != null) clearActiveRunId(); // self-heal a stale/garbage value
      return null;
    }
    return id;
  } catch {
    return null;
  }
}

export function setActiveRunId(id: string): void {
  if (!isUsableId(id)) return; // never persist an empty or stringified-nullish id
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
