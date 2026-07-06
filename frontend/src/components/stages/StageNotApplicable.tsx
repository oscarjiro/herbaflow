import { cn } from "@/lib/cn";
import { stageLabel } from "../../contract/labels";

/**
 * The one home for a stage view's "not applicable for this run" fallback: a greyed,
 * aria-disabled section headed by the stage's canonical title. Rendered by the Stage 1/2/3/4
 * views when the run's input mode makes that stage not_applicable.
 */
export function StageNotApplicable({ stage }: { stage: number }) {
  return (
    <section className="stage-view stage-view--na" aria-disabled>
      <h2>{stageLabel(stage)}</h2>
      <p className={cn("text-sm", "[color:var(--hf-fg-3)]")}>Not applicable for this run.</p>
    </section>
  );
}
