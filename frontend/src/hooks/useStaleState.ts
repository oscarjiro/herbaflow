import type { AnalysisRead } from "../api/types.gen";

/** Derives whether any stage is out-of-date and which stage to re-run from. */
export function useStaleState(data: AnalysisRead): {
  anyStale: boolean;
  rerunFrom: number | null;
} {
  const results = (data.stage_results ?? {}) as Record<string, { stale?: boolean }>;
  const anyStale = Object.values(results).some((r) => r?.stale === true);
  const rerunFrom = (data.parameters as { rerun_from?: number } | undefined)?.rerun_from ?? null;
  return { anyStale, rerunFrom };
}
