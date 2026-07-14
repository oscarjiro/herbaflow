import type { AnalysisRead } from "@/api/types.gen";

/**
 * Per-stage running verb shown in the trail t-sub while a stage is in progress.
 * Only Stages 2 & 3 emit live progress; the verb appears in the sub-label whenever
 * progress.stage matches the node's stage number.
 */
const RUNNING_VERB: Record<number, string> = {
  1: "Resolving",
  2: "Filtering",
  3: "Enriching",
  4: "Fetching",
  5: "Computing",
  6: "Mapping",
  7: "Ranking",
  8: "Enriching",
};

/**
 * Return the live running sub-label for a stage node when data.progress is present
 * and matches this stage. Falls back to the verb alone when no per-item count.
 */
export function runningSub(stage: number, data: AnalysisRead): string {
  const verb = RUNNING_VERB[stage] ?? "Working";
  const p = data.progress;
  if (p != null && p.stage === stage) {
    return `${verb} ${p.processed} / ${p.total}`;
  }
  return verb;
}

/**
 * Return the done sub-label for a stage node derived from stage_results[n].count.
 * Each stage has a `.count` field; if absent we fall back to "Done".
 */
export function doneSub(stage: number, data: AnalysisRead): string {
  const result = data.stage_results?.[String(stage)] as { count?: number } | undefined;
  const n = result?.count;
  if (n == null) return "Done";
  switch (stage) {
    case 1:
      return `${n} found`;
    case 2:
      return `${n} passed`;
    case 3:
      return `${n} targets`;
    case 4:
      return `${n} targets`;
    case 5:
      return `${n} shared`;
    case 6:
      return `${n} nodes`;
    case 7:
      return `${n} hubs`;
    case 8:
      return `${n} terms`;
    default:
      return "Done";
  }
}
