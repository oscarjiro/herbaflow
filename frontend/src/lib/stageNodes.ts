import type { AnalysisRead } from "@/api/types.gen";
import { isSlugApplicable, isSlugReached, slugToStage, type StageSlug } from "@/lib/stageRoutes";
import { runningStage } from "@/lib/runStatus";
import { doneSub, runningSub } from "@/lib/stageSummary";

export type NodeState =
  | "done"
  | "running"
  | "active"
  | "locked"
  | "not_applicable"
  | "blocked"
  | "failed";

export function nodeState(slug: StageSlug, data: AnalysisRead, activeSlug?: StageSlug): NodeState {
  if (!isSlugApplicable(slug, data)) return "not_applicable";
  const n = slugToStage(slug);
  // A failed run marks the stage it died on (current_stage) as failed — never a
  // green "done" check, which would hide that the run stopped here.
  if (data.status === "failed" && n != null && data.current_stage === n) return "failed";
  if (n != null && runningStage(data.status) === n) return "running";
  const reached = isSlugReached(slug, data);
  if (reached) {
    const result =
      n != null ? (data.stage_results?.[String(n)] as { count?: number } | undefined) : undefined;
    if (result && result.count === 0) return "blocked";
    if (slug === activeSlug) return "active";
    return "done";
  }
  if (slug === activeSlug) return "active";
  return "locked";
}

export function nodeSub(
  slug: StageSlug,
  state: NodeState,
  isDone: boolean,
  data: AnalysisRead,
): string {
  const n = slugToStage(slug);
  if (state === "failed") return "Failed";
  if (state === "running" && n != null) return runningSub(n, data);
  if (state === "locked") return "Locked";
  if (state === "not_applicable") return "N/A";
  if (isDone && n != null) return doneSub(n, data);
  if (slug === "final" && data.status === "complete") return "Complete";
  return "";
}

export function isNavigable(state: NodeState): boolean {
  return (
    state === "done" ||
    state === "active" ||
    state === "running" ||
    state === "blocked" ||
    state === "failed"
  );
}
