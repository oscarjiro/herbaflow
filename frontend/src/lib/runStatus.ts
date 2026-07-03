/**
 * Run-lifecycle status predicates (one home).
 *
 * A run's `status` is a string like `stage_3_running`, `stage_3_awaiting_approval`,
 * `complete`, or `failed`. These helpers read the "actively computing" signal off
 * that string so every consumer agrees on when the pipeline is busy.
 */

/** The stage number a run is actively computing, or null when no stage is running. */
export function runningStage(status: string | null | undefined): number | null {
  const match = /^stage_(\d+)_running$/.exec(status ?? "");
  return match ? Number(match[1]) : null;
}

/**
 * True while the pipeline is actively computing any stage (a `stage_N_running`
 * status). All recompute controls — ParamPanel Redo and the StaleNotice
 * "Re-run from Step N" — are disabled while the run is busy so a redo can't be
 * fired mid-run (the backend also rejects it; this is the UI guard).
 */
export function isRunBusy(status: string | null | undefined): boolean {
  return runningStage(status) != null;
}
