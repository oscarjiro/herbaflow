import { useMemo } from "react";

/** CSV-escape one cell: null/undefined -> "", quote+double when it contains , " or newline. */
export function escapeCsv(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/** Build a CSV string from a header line and rows of cells (each cell escaped). */
export function buildCsv(header: string, rows: readonly unknown[][]): string {
  const body = rows.map((cells) => cells.map(escapeCsv).join(",")).join("\n");
  return `${header}\n${body}`;
}

/**
 * Memoized object URL for a CSV blob built from `header` + `rows`.
 *
 * Keyed on the built CSV string (stable by value), not the `rows` array, so a
 * caller passing a freshly-built `rows` array each render does not churn a new
 * object URL (and leak the old one) on every render — only when content changes.
 */
export function useCsvBlobUrl(header: string, rows: readonly unknown[][]): string {
  const csv = buildCsv(header, rows);
  return useMemo(() => URL.createObjectURL(new Blob([csv], { type: "text/csv" })), [csv]);
}
