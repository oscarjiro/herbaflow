import type { AnalysisRead } from "@/api/types.gen";
import { Eyebrow } from "@/components/ui/editorial";
import { Button } from "@/components/ui/button";
import { ApprovalBar } from "@/components/stages/ApprovalBar";
import { StaleNotice } from "@/components/stages/StaleNotice";
import { RunFailedNotice } from "@/components/stages/RunFailedNotice";
import { StageRunningSkeleton } from "@/components/stages/StageRunningSkeleton";
import { useStaleState } from "@/hooks/useStaleState";
import { isRunBusy } from "@/lib/runStatus";
import { emptyIsValidResult } from "@/lib/stageAddability";

type StageResult = { count?: number } | undefined;

export function StageView({
  data,
  stage,
  title,
  kicker,
  description,
  onApprove,
  approvePending,
  onEdit,
  canAddWhenEmpty = false,
  children,
}: {
  data: AnalysisRead;
  stage: number;
  title: string;
  kicker: string;
  description?: string;
  onApprove: () => Promise<void>;
  approvePending: boolean;
  onEdit?: () => void;
  canAddWhenEmpty?: boolean;
  children: React.ReactNode;
}) {
  const { anyStale, rerunFrom } = useStaleState(data);
  const result = data.stage_results?.[String(stage)] as StageResult;
  const hasResult = result != null;
  const isEmpty = hasResult && (result?.count ?? 0) === 0;
  // Terminal analytical stages (6-8) can legitimately produce zero items; that is a real result,
  // not a dead-end. Keep Approve enabled so the run can still complete, and let the stage render
  // its own no-results panel instead of the generic dead-end block.
  const emptyResult = emptyIsValidResult(stage);
  const isDeadEnd = isEmpty && !canAddWhenEmpty && !emptyResult;
  // A failed run has no results for the stage it died on (or any later stage). Show
  // the failure + re-run affordance instead of a blank stage body. reset-from points
  // at the stage that actually failed (current_stage), not the stage being viewed.
  const isFailedView = data.status === "failed" && !hasResult;
  // A reached stage with no result yet is still computing. Drive the skeleton off
  // "no result" rather than an exact `stage_N_running` status match: a fresh run
  // passes through pre-result states (created, or the tick before the poll flips to
  // running) where the old check briefly rendered an empty 0-item stage body.
  const isRunning = !hasResult && !isFailedView;
  const failedStage = data.current_stage ?? stage;

  return (
    <section className="flex flex-col gap-5">
      <header className="flex flex-col gap-1">
        <Eyebrow>{kicker}</Eyebrow>
        <h1 className="font-display text-hf-fg-1 text-3xl tracking-tight">{title}</h1>
        {description && <p className="text-hf-fg-3 text-sm">{description}</p>}
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
      ) : isFailedView ? (
        <RunFailedNotice
          analysisId={data.analysis_id}
          failedStage={failedStage}
          message={data.error_message}
        />
      ) : isDeadEnd ? (
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
          {isEmpty && !emptyResult && (
            <div
              role="status"
              className="border-hf-border bg-hf-surface text-hf-fg-2 rounded-[var(--radius-lg)] border p-4 text-sm"
            >
              This step produced no results yet. Add an item below to continue.
            </div>
          )}
          {children}
          {rerunFrom === stage && (
            <StaleNotice
              analysisId={data.analysis_id}
              fromStage={rerunFrom}
              disabled={isRunBusy(data.status)}
            />
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
              disabled={(isEmpty && !emptyResult) || anyStale}
              disabledReason={
                anyStale ? "Run the updated step before continuing." : "Add an item to continue."
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
