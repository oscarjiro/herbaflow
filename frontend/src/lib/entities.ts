/**
 * True when an entity row was soft-removed by the user (its durable `user-removed` tag). Such rows
 * are hidden from every entity list but kept in the data for re-run / Stage-5 both-sides exclusion;
 * undo = re-add via the add box.
 */
export function isUserRemoved(tag?: string | null): boolean {
  return tag === "user-removed";
}

/**
 * True when an entity stage is at its floor of one visible entity, so the last remaining row's
 * remove control must be disabled (the backend also 422s the last removal).
 */
export function atMinEntities(effectiveCount: number): boolean {
  return effectiveCount <= 1;
}

// A run has compounds unless its plant side is the target-only manual mode.
export function runHasCompounds(
  run: { parameters?: { input_modes?: { plant?: string } } } | null | undefined,
): boolean {
  const plant = run?.parameters?.input_modes?.plant ?? "selection";
  return plant !== "manual_targets";
}

/**
 * True when the run's C-T-P output is emittable: it has compounds, a non-empty Stage-5
 * overlap (count > 0), AND non-empty Stage-8 pathways (count > 0).
 *
 * Mirrors the backend ``ctp_is_emittable`` predicate. Use this to hide the C-T-P graph and
 * network.zip download when the combined gate is false (PPI is unaffected and must stay shown).
 */
export function runHasCtp(
  run:
    | {
        parameters?: { input_modes?: { plant?: string } };
        stage_results?: { [key: string]: unknown };
      }
    | null
    | undefined,
): boolean {
  if (!runHasCompounds(run)) return false;
  const sr = run?.stage_results ?? {};
  const overlap = (sr["5"] as { count?: number } | null | undefined)?.count ?? 0;
  const terms = (sr["8"] as { count?: number } | null | undefined)?.count ?? 0;
  return overlap > 0 && terms > 0;
}

/**
 * Merge `incoming` items into `existing`, deduplicating by the given id key.
 * Existing items come first; genuinely new items are appended in their original order.
 * Pure — returns a new array; never mutates either input.
 */
export function mergeById<T extends Record<string, unknown>>(
  existing: T[],
  incoming: T[],
  idKey: keyof T,
): T[] {
  const seen = new Set(existing.map((item) => item[idKey]));
  const genuinelyNew = incoming.filter((item) => !seen.has(item[idKey]));
  return [...existing, ...genuinelyNew];
}
