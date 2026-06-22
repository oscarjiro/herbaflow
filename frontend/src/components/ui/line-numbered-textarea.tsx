import * as React from "react";
import { cn } from "@/lib/cn";

export type LineNumberedTextareaProps = {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  /** 1-based line number -> reason string, for error markers in the gutter */
  errorLines?: ReadonlyMap<number, string>;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  "aria-label"?: string;
};

/**
 * Custom line-numbered textarea (Software Lock §5.2 — not CodeMirror/Monaco).
 *
 * Renders a left gutter of 1-based line numbers, one per line of `value`,
 * synchronised to the textarea's vertical scroll. Lines whose numbers appear
 * in `errorLines` are rendered as "!" in `text-destructive` with the reason as
 * a `title` tooltip.
 *
 * The ref (if provided) is forwarded to the underlying `<textarea>` element so
 * callers can focus it and move the caret for jump-to-line behaviour.
 *
 * jsdom cannot measure layout, so the gutter is N `<span>` elements rendered
 * deterministically. Scroll-sync is a best-effort `onScroll` handler that
 * no-ops safely in test environments.
 */
export const LineNumberedTextarea = React.forwardRef<
  HTMLTextAreaElement,
  LineNumberedTextareaProps
>(function LineNumberedTextarea(
  { id, value, onChange, errorLines, placeholder, rows = 3, disabled, "aria-label": ariaLabel },
  ref,
) {
  const gutterRef = React.useRef<HTMLDivElement>(null);

  const lines = value.split("\n");
  const lineCount = Math.max(lines.length, 1);

  function handleScroll(e: React.UIEvent<HTMLTextAreaElement>) {
    if (gutterRef.current) {
      gutterRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  }

  return (
    <div
      data-slot="manual-paste"
      className={cn(
        "border-input focus-within:border-ring focus-within:ring-ring/50 flex w-full max-h-64 scroll overflow-hidden rounded-md border bg-transparent shadow-xs transition-[color,box-shadow] focus-within:ring-[3px]",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      {/* Gutter — aria-hidden; purely decorative line numbers */}
      <div
        ref={gutterRef}
        aria-hidden="true"
        data-testid="line-gutter"
        className="bg-muted/40 text-muted-foreground flex min-w-10 shrink-0 flex-col overflow-hidden border-r px-2 py-2 font-mono text-sm leading-5 tabular-nums select-none"
      >
        {Array.from({ length: lineCount }, (_, i) => {
          const lineNum = i + 1;
          const hasError = errorLines?.has(lineNum) ?? false;
          const errorReason = errorLines?.get(lineNum);
          return (
            <span
              key={lineNum}
              title={hasError ? errorReason : undefined}
              className={cn(
                "block text-right leading-5",
                hasError ? "text-destructive font-semibold" : "text-muted-foreground",
              )}
            >
              {hasError ? "!" : lineNum}
            </span>
          );
        })}
      </div>

      {/* Textarea */}
      <textarea
        ref={ref}
        id={id}
        aria-label={ariaLabel}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={handleScroll}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        className="placeholder:text-muted-foreground flex min-h-[5rem] w-full resize-none bg-transparent px-3 py-2 font-mono text-sm leading-5 outline-none disabled:cursor-not-allowed"
        spellCheck={false}
      />
    </div>
  );
});
