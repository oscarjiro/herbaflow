import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// BoolMark — compact true/false/null indicator for table cells
// ---------------------------------------------------------------------------

interface BoolMarkProps {
  value: boolean | null | undefined;
  className?: string;
}

function BoolMark({ value, className }: BoolMarkProps) {
  if (value === true) {
    return (
      <span aria-label="Yes" className={cn("text-hf-success inline-block select-none", className)}>
        ✓
      </span>
    );
  }

  if (value === false) {
    return (
      <span aria-label="No" className={cn("text-hf-danger inline-block select-none", className)}>
        ✗
      </span>
    );
  }

  // null or undefined
  return (
    <span
      aria-label="Not applicable"
      className={cn("text-hf-fg-4 inline-block select-none", className)}
    >
      &ndash;
    </span>
  );
}

export { BoolMark };
export type { BoolMarkProps };
