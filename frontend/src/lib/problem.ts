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
// being temporarily over its usage limit (402). The UI shows the full
// "service unavailable" screen for these rather than retrying inline.
const SERVICE_OUTAGE_STATUS = new Set([402, 503]);

export function isServiceOutage(err: Problem | undefined | null): boolean {
  const status = err?.status;
  return status != null && SERVICE_OUTAGE_STATUS.has(status);
}
