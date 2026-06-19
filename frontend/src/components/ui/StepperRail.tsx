import type { AnalysisRead } from "@/api/types.gen";
import { STAGE_LABELS } from "@/contract/labels";
import { cn } from "@/lib/cn";

type StepState = "done" | "current" | "pending" | "not_applicable";

/** Parse the awaiting stage number from a status like "3_awaiting_approval". */
function awaitingStage(status: string | null): number | null {
  if (!status) return null;
  const m = status.match(/^(\d+)_awaiting_approval$/);
  return m?.[1] != null ? parseInt(m[1], 10) : null;
}

function deriveStepState(n: number, data: AnalysisRead, currentStage: number | null): StepState {
  // stage_state carries the entry-mode-intended state ("not_applicable" for N/A stages).
  if (data.stage_state?.[String(n)] === "not_applicable") {
    return "not_applicable";
  }
  if (n === currentStage) {
    return "current";
  }
  const hasResult = Boolean(data.stage_results?.[String(n)]);
  if (hasResult || (currentStage !== null && n < currentStage)) {
    return "done";
  }
  return "pending";
}

export function StepperRail({ data, className }: { data: AnalysisRead; className?: string }) {
  const awaiting = awaitingStage(data.status);
  // Use the awaiting stage, then fall back to current_stage from the run.
  const currentStage = awaiting ?? data.current_stage;

  return (
    <nav aria-label="Pipeline steps" className={cn("w-full", className)}>
      <ol className="flex flex-row gap-1 overflow-x-auto lg:flex-col lg:gap-2">
        {STAGE_LABELS.map((label, i) => {
          const n = i + 1;
          const state = deriveStepState(n, data, currentStage);
          const isCurrent = state === "current";
          const isDone = state === "done";
          const isNA = state === "not_applicable";

          return (
            <li
              key={n}
              aria-current={isCurrent ? "step" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                isCurrent && "bg-hf-surface text-hf-fg-1 ring-hf-border font-semibold ring-1",
                isDone && "text-hf-fg-2",
                state === "pending" && "text-hf-fg-3",
                isNA && "text-hf-fg-3 line-through opacity-50",
              )}
            >
              <span
                className={cn(
                  "border-hf-border flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs",
                  isCurrent && "bg-hf-surface border-current",
                  isDone && "border-hf-border bg-hf-surface",
                  (state === "pending" || isNA) && "opacity-60",
                )}
              >
                {isDone ? "✓" : n}
              </span>
              <span className="leading-tight">{label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
