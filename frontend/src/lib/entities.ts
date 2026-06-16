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
