import * as React from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Chip — removable entity chip (label + focusable × button)
// ---------------------------------------------------------------------------

interface ChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** The visible label text. */
  label: string;
  /** Called when the × button is activated. */
  onRemove: () => void;
}

function Chip({ label, onRemove, className, ...props }: ChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-[7px] rounded-[var(--radius-pill)] border border-hf-border bg-hf-surface-2 py-[5px] pl-[13px] pr-[7px] text-[13px]",
        className,
      )}
      {...props}
    >
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label}`}
        className={cn(
          "inline-flex size-[18px] cursor-pointer items-center justify-center rounded-full text-hf-fg-3",
          "transition-colors duration-[var(--duration-1)]",
          "hover:bg-hf-neutral-300 hover:text-hf-fg-1",
          "focus-visible:outline-[1.5px] focus-visible:outline-hf-fg-1 focus-visible:outline-offset-1",
        )}
      >
        {/* × character — not an em dash, not a real × entity — just plain multiply sign */}
        &#xD7;
      </button>
    </span>
  );
}

// ---------------------------------------------------------------------------
// OverflowChip — "+N more" indicator for truncated lists
// ---------------------------------------------------------------------------

interface OverflowChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Number of hidden items. */
  count: number;
}

function OverflowChip({ count, className, ...props }: OverflowChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--radius-pill)] border border-hf-border bg-hf-surface-2 px-[13px] py-[5px] text-[13px] text-hf-fg-3",
        className,
      )}
      {...props}
    >
      +{count} more
    </span>
  );
}

export { Chip, OverflowChip };
export type { ChipProps, OverflowChipProps };
