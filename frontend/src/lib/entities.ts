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
