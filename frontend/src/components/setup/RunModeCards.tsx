import { Check } from "lucide-react";
import { GlassSurface } from "@/components/ui/GlassSurface";
import { cn } from "@/lib/cn";

const MODES = [
  { value: "guided" as const, title: "Guided", blurb: "Review and approve each step." },
  { value: "auto" as const, title: "Automatic", blurb: "Run end to end, then review." },
];

// Run-mode picker as selection cards: selected = elevated brighter body + filled check, no
// tint/ring/border. Maps to the contract `mode` enum.
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
          <GlassSurface
            key={m.value}
            tier="raised"
            className={cn(
              "cursor-pointer rounded-[var(--radius-lg)] p-4 transition-shadow",
              selected ? "shadow-md" : "opacity-90 hover:opacity-100",
            )}
          >
            <button
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(m.value)}
              className="flex w-full items-start gap-3 text-left outline-none"
            >
              <span
                className={cn(
                  "border-hf-border mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
                  selected && "border-hf-accent bg-hf-accent text-hf-bg",
                )}
              >
                {selected && <Check className="size-3.5" aria-hidden="true" />}
              </span>
              <span className="flex flex-col gap-1">
                <span className="text-hf-fg-1 font-medium">{m.title}</span>
                <span className="text-hf-fg-3 text-sm">{m.blurb}</span>
              </span>
            </button>
          </GlassSurface>
        );
      })}
    </div>
  );
}
