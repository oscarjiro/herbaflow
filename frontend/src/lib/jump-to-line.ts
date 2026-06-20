/**
 * Best-effort focus + caret jump to the start of the given 1-based line.
 * Computed by summing char lengths of all preceding lines + their newlines.
 * No-ops silently on a null element or in jsdom (where setSelectionRange may
 * not move the caret).
 */
export function jumpToLine(el: HTMLTextAreaElement | null, text: string, lineNum: number): void {
  if (!el) return;
  const lines = text.split("\n");
  let offset = 0;
  for (let i = 0; i < lineNum - 1 && i < lines.length; i++) {
    offset += (lines[i]?.length ?? 0) + 1; // +1 for the newline
  }
  try {
    el.focus();
    el.setSelectionRange(offset, offset);
  } catch {
    // jsdom or older browsers may not support this — no-op
  }
}
