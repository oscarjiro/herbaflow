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
