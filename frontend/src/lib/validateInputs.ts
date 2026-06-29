/**
 * Dedup helper for manual validate inputs, with the original position of each
 * distinct entry.
 *
 * Trims each item's `.value`, drops empty/whitespace-only entries, and returns
 * the first-seen object for each distinct trimmed value. `lines[i]` is the
 * 1-based index of `items[i]` in the ORIGINAL `inputs` array (its first
 * occurrence), so a caller that built `inputs` from textarea lines can map a
 * resolved/failed result back to the exact line the user typed — even after
 * dedup reorders/drops rows and after the request is split into batches.
 *
 * This is the ONE canonical home for pre-send dedup — used at every call site
 * that builds an inputs array for /compounds/validate or /targets/validate
 * (CompoundValidateBox, TargetValidateBox, StpDialog).
 */
export function distinctInputsWithOrigin<T extends { value: string }>(
  inputs: T[],
): { items: T[]; lines: number[] } {
  const seen = new Set<string>();
  const items: T[] = [];
  const lines: number[] = [];
  inputs.forEach((item, idx) => {
    const trimmed = item.value.trim();
    if (!trimmed) return;
    if (seen.has(trimmed)) return;
    seen.add(trimmed);
    items.push(item);
    lines.push(idx + 1); // 1-based line of the first occurrence
  });
  return { items, lines };
}

/** Distinct inputs only (drops the origin-line bookkeeping). */
export function distinctInputs<T extends { value: string }>(inputs: T[]): T[] {
  return distinctInputsWithOrigin(inputs).items;
}
