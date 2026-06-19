import { Skeleton } from "@/components/ui/skeleton";
import { stageLabel } from "@/contract/labels";

export function StageRunningSkeleton({ stage }: { stage: number }) {
  const label = stageLabel(stage);
  return (
    <section aria-label={`Step ${stage} running`}>
      <h2 className="text-hf-fg-1 mb-3 text-lg font-semibold">
        Step {stage} — {label}
        <span className="text-hf-fg-3 ml-1 text-sm font-normal"> · running…</span>
      </h2>
      <div className="border-hf-border overflow-hidden rounded-[var(--radius-3)] border">
        <div className="bg-hf-surface/40 space-y-2 p-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>
    </section>
  );
}
