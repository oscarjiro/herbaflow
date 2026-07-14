import type { AnalysisRead } from "@/api/types.gen";
import { runHasCompounds } from "@/lib/entities";

/**
 * Whether an *empty* stage is recoverable by adding an item (render the normal stage view + add
 * affordances, Approve blocked) versus a terminal dead-end. Entity stages 1/3/4 only: stage 3 needs
 * compounds upstream (no compounds = no basis to find targets for); stages 1 and 4 can always add.
 * Computed / terminal stages (2, 5-8) keep their existing behavior.
 */
export function canAddWhenEmpty(stage: number, run: AnalysisRead): boolean {
  switch (stage) {
    case 1:
      return true;
    case 3:
      return runHasCompounds(run);
    case 4:
      return true;
    default:
      return false;
  }
}

/**
 * Whether an *empty* stage is a legitimate terminal result (approve stays enabled, the stage
 * renders its own no-results panel) rather than a dead-end. The final analytical stages can
 * honestly produce zero items: the protein network (6) may have no edges, hub ranking (7) no
 * hubs, and functional enrichment (8) no terms passing the significance threshold. A zero here
 * is a real scientific outcome, not a blocker, so the run must still be completable. Earlier
 * stages keep dead-end behavior: an empty overlap or filtered-out compound set has no basis to
 * continue and should stop the run.
 */
export function emptyIsValidResult(stage: number): boolean {
  return stage === 6 || stage === 7 || stage === 8;
}
