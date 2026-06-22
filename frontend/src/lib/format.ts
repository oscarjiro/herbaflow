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

// Short relative time for the run-identity meta line. The single relative-time home.
export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto", style: "short" });
  const mins = Math.round(diffMs / 60000);
  if (Math.abs(mins) < 60) return rtf.format(-mins, "minute");
  const hours = Math.round(mins / 60);
  if (Math.abs(hours) < 24) return rtf.format(-hours, "hour");
  const days = Math.round(hours / 24);
  return rtf.format(-days, "day");
}
