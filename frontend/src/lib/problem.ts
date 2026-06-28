export type Problem = {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  errors?: { detail?: string; pointer?: string }[];
};

export function humanizeProblem(p: Problem | undefined | null): string {
  if (!p) return "Something went wrong. Please try again.";
  if (p.detail) return p.detail;
  if (p.errors?.length && p.errors[0]?.detail) return p.errors[0].detail ?? "";
  if (p.title) return p.title;
  return "Something went wrong. Please try again.";
}

// Statuses that mean the backend is reachable but its data store is not: a brief
// database outage (mapped from a raw connect error to 503) or the hosted database
// being temporarily over its usage limit (402).
const STORE_DOWN_STATUS = new Set([402, 503]);

/**
 * True when a poll/health error means the backend cannot currently be reached, so
 * the UI should show the full "service unavailable" screen (Retry) instead of
 * retrying inline forever:
 *  - a transport failure — the thrown error carries no HTTP `status` because no
 *    response ever arrived (the backend process is down, connection refused, DNS
 *    failure, etc.);
 *  - a store-down status (402 / 503) — the backend answered but its database is not.
 *
 * Self-healable statuses (404 gone, 422 malformed id) are NOT hard-down: the caller
 * clears those back to setup. A nullish error (no error at all) is not down.
 */
export function isHardDown(err: Problem | undefined | null): boolean {
  if (err == null) return false;
  const status = err.status;
  if (status == null) return true; // transport failure: no HTTP response arrived
  return STORE_DOWN_STATUS.has(status);
}
