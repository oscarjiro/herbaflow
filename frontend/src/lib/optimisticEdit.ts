import type { AnalysisRead } from "../api/types.gen";

/**
 * Maps a stage number to the list key and id key within `stage_results[stage]`.
 * Only stages 1, 3, and 4 are editable entity stages.
 */
const STAGE_ENTITY_MAP: Record<number, { listKey: string; idKey: string }> = {
  1: { listKey: "compounds", idKey: "compound_id" },
  3: { listKey: "targets", idKey: "target_id" },
  4: { listKey: "targets", idKey: "target_id" },
};

/**
 * Return a new AnalysisRead with the given entity ids marked tag:"user-removed"
 * in the stage's entity list. Immutable: copies only the touched levels; never
 * mutates the input. Unknown stage / missing list returns the run unchanged.
 */
export function markEntitiesRemoved(
  run: AnalysisRead,
  stage: number,
  ids: readonly string[],
): AnalysisRead {
  const mapping = STAGE_ENTITY_MAP[stage];
  if (!mapping) return run;

  const stageKey = String(stage);
  const stageResult = (run.stage_results as Record<string, unknown> | null | undefined)?.[stageKey];
  if (!stageResult || typeof stageResult !== "object") return run;

  const list = (stageResult as Record<string, unknown>)[mapping.listKey];
  if (!Array.isArray(list)) return run;

  const idSet = new Set(ids);
  const newList = list.map((item: unknown) => {
    if (!item || typeof item !== "object") return item;
    const row = item as Record<string, unknown>;
    if (idSet.has(row[mapping.idKey] as string)) {
      return { ...row, tag: "user-removed" };
    }
    return row;
  });

  return {
    ...run,
    stage_results: {
      ...(run.stage_results as Record<string, unknown>),
      [stageKey]: {
        ...(stageResult as Record<string, unknown>),
        [mapping.listKey]: newList,
      },
    },
  } as AnalysisRead;
}
