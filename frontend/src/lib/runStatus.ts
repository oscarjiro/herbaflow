/**
 * Single home for converting a raw analysis status string into a human-readable label.
 * Consumed by RunView (run header badge) and RecentRuns (list row badge).
 */
export function formatRunStatus(status: string | null | undefined): string {
  if (!status) return "Unknown";
  if (status === "complete") return "Complete";
  if (status === "failed") return "Failed";

  const stageMatch = /^stage_(\d+)_(.+)$/.exec(status);
  if (stageMatch) {
    const [, stage, state] = stageMatch;
    if (state === "awaiting_approval") return "Waiting for review";
    return `Running step ${stage}`;
  }

  const readable = status.replaceAll("_", " ");
  return readable.charAt(0).toUpperCase() + readable.slice(1);
}
