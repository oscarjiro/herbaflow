import { cn } from "@/lib/cn";

export type SegmentOption<T extends string> = { value: T; label: string };

// Segmented control for a small, mutually-exclusive choice (per-side input mode). A real
// radiogroup for keyboard/AT. Selected = brighter elevated body, no tint/ring/border.
// Stays SOLID (this sits inside a glass panel).
export function SegmentedTabs<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: SegmentOption<T>[];
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "bg-hf-surface-2 border-hf-border inline-flex gap-1 rounded-[var(--radius-md)] border p-1",
        className,
      )}
    >
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(opt.value)}
            className={cn(
              "rounded-[var(--radius-sm)] px-3 py-1.5 text-sm transition-colors",
              selected ? "bg-hf-surface text-hf-fg-1 shadow-sm" : "text-hf-fg-3 hover:text-hf-fg-1",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
