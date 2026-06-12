/**
 * Format a number for ON-SCREEN display at `sig` significant figures (default 4), trimming
 * trailing zeros. Returns "—" for null/undefined/NaN. Display-only: CSV exports keep the
 * raw unrounded value, so this is never used in the `lib/csv` row builders.
 */
export function formatSig(value: number | null | undefined, sig = 4): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value === 0) return "0";
  return String(Number(value.toPrecision(sig)));
}
