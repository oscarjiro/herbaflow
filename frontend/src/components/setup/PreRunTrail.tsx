import { STAGE_SLUGS, slugToStage, type StageSlug } from "@/lib/stageRoutes";
import { stageLabel } from "@/contract/labels";
import { cn } from "@/lib/cn";

function slugLabel(slug: StageSlug): string {
  if (slug === "inputs") return "Inputs";
  if (slug === "final") return "Final";
  const n = slugToStage(slug);
  return n != null ? stageLabel(n) : slug;
}

// Pre-run setup trail: "Inputs" is the active step; the eight stages + Final are shown as upcoming.
// Static and non-navigable (no run exists yet, so no per-stage routes to link to).
export function PreRunTrail() {
  return (
    <nav aria-label="Pipeline steps" className="w-full">
      <ol className="scroll flex flex-row gap-1 overflow-x-auto lg:flex-col lg:gap-1.5 lg:overflow-x-visible">
        {STAGE_SLUGS.map((slug) => {
          const active = slug === "inputs";
          return (
            <li
              key={slug}
              aria-current={active ? "step" : undefined}
              aria-disabled={active ? undefined : "true"}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm",
                active ? "bg-hf-surface text-hf-fg-1 font-semibold" : "text-hf-fg-3 opacity-60",
              )}
            >
              <span
                className={cn(
                  "border-hf-border flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs",
                  active ? "ring-hf-sage-deep border-current ring-2" : "opacity-50",
                )}
                aria-hidden="true"
              />
              <span className="truncate">{slugLabel(slug)}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
