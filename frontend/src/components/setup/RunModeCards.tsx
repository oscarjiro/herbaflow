import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

const MODES = [
  { value: "guided" as const, title: "Guided", blurb: "Review and approve each step." },
  { value: "auto" as const, title: "Automatic", blurb: "Run end to end, then review." },
];

// Run-mode picker as solid selection cards: controls stay solid (glass = chrome/overlay only).
// Selected = shadow + 1px lift + filled ink check, no tint/ring/border-color highlight.
export function RunModeCards({
  value,
  onChange,
}: {
  value: "guided" | "auto";
  onChange: (v: "guided" | "auto") => void;
}) {
  return (
    <div role="radiogroup" aria-label="Run mode" className="grid gap-3 sm:grid-cols-2">
      {MODES.map((m) => {
        const selected = m.value === value;
        return (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={selected}
            data-selected={selected || undefined}
            onClick={() => onChange(m.value)}
            className={cn(
              "bg-hf-surface border-hf-border-strong rounded-[var(--radius-md)] border p-4 text-left transition-all",
              "hover:border-hf-fg-3",
              selected && "-translate-y-px shadow-[var(--hf-glass-shadow)]",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-hf-fg-1 text-sm font-semibold">{m.title}</span>
              <span
                className={cn(
                  "grid size-[19px] place-items-center rounded-full border-[1.5px]",
                  selected
                    ? "border-hf-fg-1 bg-hf-fg-1 text-hf-bg"
                    : "border-hf-border-strong text-transparent",
                )}
              >
                <Check className="size-3" strokeWidth={3} aria-hidden="true" />
              </span>
            </div>
            <p className="text-hf-fg-3 mt-1.5 text-sm leading-snug">{m.blurb}</p>
          </button>
        );
      })}
    </div>
  );
}
