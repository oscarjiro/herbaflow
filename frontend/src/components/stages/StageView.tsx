import type { AnalysisRead } from "@/api/types.gen";
import { Eyebrow } from "@/components/ui/editorial";
import { Button } from "@/components/ui/button";
import { ApprovalBar } from "@/components/stages/ApprovalBar";
import { StaleNotice } from "@/components/stages/StaleNotice";
import { StageRunningSkeleton } from "@/components/stages/StageRunningSkeleton";
import { useStaleState } from "@/hooks/useStaleState";

type StageResult = { count?: number } | undefined;

export function StageView({
  data,
  stage,
  title,
  kicker,
  onApprove,
  approvePending,
  onEdit,
  children,
}: {
  data: AnalysisRead;
  stage: number;
  title: string;
  kicker: string;
  onApprove: () => Promise<void>;
  approvePending: boolean;
  onEdit?: () => void;
  children: React.ReactNode;
}) {
  const { anyStale, rerunFrom } = useStaleState(data);
  const result = data.stage_results?.[String(stage)] as StageResult;
  const isRunning = data.status === `stage_${stage}_running` && !result;
  const isEmpty = Boolean(result) && (result?.count ?? 0) === 0;

  return (
    <section className="flex flex-col gap-5">
      <header className="flex flex-col gap-1">
        <Eyebrow>{kicker}</Eyebrow>
        <h1 className="font-display text-hf-fg-1 text-3xl tracking-tight">{title}</h1>
      </header>

      {isRunning ? (
        <>
          {data.progress && data.progress.stage === stage ? (
            /* Stages 2 & 3 emit per-item progress — gradient pulse fill */
            <div className="flex flex-col gap-2">
              <div className="progress-top flex items-baseline justify-between">
                <span className="working-label text-hf-fg-1 text-[0.9rem]">Working</span>
                <span className="text-hf-fg-2 text-[0.9rem] font-semibold tabular-nums">
                  {data.progress.processed} / {data.progress.total}
                </span>
              </div>
              <div className="progress-bar w-full">
                <div
                  className="progress-fill"
                  style={{
                    width: `${data.progress.total ? (data.progress.processed / data.progress.total) * 100 : 0}%`,
                  }}
                  aria-valuenow={data.progress.processed}
                  aria-valuemax={data.progress.total}
                  role="progressbar"
                />
              </div>
            </div>
          ) : (
            /* Stages 1, 4–8 have no per-item progress — shimmer skeleton */
            <div
              aria-label={`Step ${stage} loading`}
              aria-busy="true"
              className="flex flex-col gap-3"
            >
              <div className="sk sk--wide" style={{ width: "60%" }} />
              <div className="sk sk--mid" style={{ width: "85%" }} />
              <div className="sk sk--narrow" style={{ width: "45%" }} />
            </div>
          )}
          <StageRunningSkeleton stage={stage} />
        </>
      ) : isEmpty ? (
        <div
          role="status"
          className="border-hf-border bg-hf-surface flex flex-col gap-3 rounded-[var(--radius-lg)] border p-6"
        >
          <p className="text-hf-fg-1 font-medium">No results at this step.</p>
          <p className="text-hf-fg-3 text-sm">
            This step finished without producing any items, so the run is paused here. Add an item
            to continue, or go back and adjust the inputs.
          </p>
          {onEdit && (
            <div>
              <Button variant="secondary" size="sm" onClick={onEdit}>
                Edit / add
              </Button>
            </div>
          )}
        </div>
      ) : (
        <>
          {children}
          {rerunFrom === stage && (
            <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
          )}
          <div className="flex items-center gap-3">
            {onEdit && (
              <Button variant="secondary" size="sm" onClick={onEdit}>
                Edit / add
              </Button>
            )}
            <ApprovalBar
              stage={stage}
              status={data.status}
              currentStage={data.current_stage}
              disabled={(result?.count ?? 0) === 0 || anyStale}
              disabledReason={
                anyStale
                  ? "Run the updated step before continuing."
                  : "No results to continue with."
              }
              pending={approvePending}
              onApprove={onApprove}
            />
          </div>
        </>
      )}
    </section>
  );
}
