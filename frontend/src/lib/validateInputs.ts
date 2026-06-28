/**
 * Dedup helper for manual validate inputs.
 *
 * Trims each item's `.value`, drops empty/whitespace-only entries,
 * and returns the first-seen object for each distinct trimmed value.
 * Extra fields on the object (e.g. `type: "uniprot"`) are preserved
 * from the first-seen object unchanged.
 *
 * This is the ONE canonical home for pre-send dedup — used at every
 * call site that builds an inputs array for /compounds/validate or
 * /targets/validate (CompoundValidateBox, TargetValidateBox, StpDialog).
 */
export function distinctInputs<T extends { value: string }>(inputs: T[]): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of inputs) {
    const trimmed = item.value.trim();
    if (!trimmed) continue;
    if (seen.has(trimmed)) continue;
    seen.add(trimmed);
    result.push(item);
  }
  return result;
}
