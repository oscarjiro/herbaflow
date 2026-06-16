import { useMutation, useQueryClient } from "@tanstack/react-query";
import { advanceAnalysis } from "../api/sdk.gen";
import { useAnalysisStatus } from "../hooks/useAnalysisStatus";
import { useEntitySubjects } from "../hooks/useEntitySubjects";
import { useStaleState } from "../hooks/useStaleState";
import { exportArtifactUrl } from "../lib/exportUrl";
import { runHasCompounds } from "../lib/entities";
import { ApprovalBar } from "./stages/ApprovalBar";
import { Stage1View } from "./stages/Stage1View";
import { Stage2View } from "./stages/Stage2View";
import { Stage3View } from "./stages/Stage3View";
import { Stage4View } from "./stages/Stage4View";
import { Stage5View } from "./stages/Stage5View";
import { Stage6View } from "./stages/Stage6View";
import { Stage7View } from "./stages/Stage7View";
import { Stage8View } from "./stages/Stage8View";
import { StaleNotice } from "./stages/StaleNotice";
import { DownloadResults } from "./DownloadResults";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Eyebrow } from "@/components/ui/editorial";
import { StepperRail } from "@/components/ui/StepperRail";

/** Returns true when the run is settled (not actively executing a stage). */
function isSettled(status: string | null | undefined): boolean {
  if (!status) return false;
  return status.endsWith("awaiting_approval") || status === "complete" || status === "failed";
}

type Stage1Data = {
  count?: number;
  compounds?: { compound_id: string; canonical_name?: string | null; tag?: string }[];
  state?: string;
};

export function RunView({ analysisId, onReset }: { analysisId: string; onReset?: () => void }) {
  const { data } = useAnalysisStatus(analysisId);
  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: async () => advanceAnalysis({ path: { analysis_id: analysisId } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const { plant: plantDisplay, disease: diseaseDisplay } = useEntitySubjects(data);

  if (!data)
    return (
      <div className="flex flex-col gap-3 p-6">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-48" />
      </div>
    );

  // stage1 is still used below for the inline (unsettled) fallback rendering and ApprovalBar.
  const stage1 = data.stage_results?.["1"] as Stage1Data | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  return (
    <div className="lg:grid lg:grid-cols-[16rem_1fr] lg:gap-8">
      {/* Left rail — sticky on large screens, horizontal on small */}
      <aside className="mb-6 self-start lg:sticky lg:top-6 lg:mb-0">
        <StepperRail data={data} />
      </aside>

      {/* Right column — main content */}
      <section className="flex min-w-0 flex-col gap-6">
        {/* Editorial header */}
        <header className="flex flex-col gap-2">
          <Eyebrow>ANALYSIS</Eyebrow>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              Run <span className="text-hf-fg-3 font-mono text-base">{analysisId}</span>
            </h1>
            <Badge variant="outline" className="capitalize">
              {data.status}
            </Badge>
          </div>
          <p className="text-hf-fg-3 text-sm">
            Plant: {plantDisplay} · Disease: {diseaseDisplay}
          </p>
        </header>

        <DownloadResults
          status={data.status}
          analysisId={analysisId}
          hasCompounds={runHasCompounds(data)}
        />

        {data.status === "complete" && runHasCompounds(data) && (
          <img
            className="border-hf-border max-w-full rounded-[var(--radius-3)] border"
            alt="Compound-target-pathway network"
            src={exportArtifactUrl(analysisId, "ctp-network.png")}
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
        )}

        {data.status === "failed" && (
          <div
            role="alert"
            className="border-hf-danger/30 bg-hf-danger-soft/20 flex flex-col gap-3 rounded-[var(--radius-3)] border p-4"
          >
            <p className="text-hf-fg-1 text-sm">{data.error_message}</p>
            {onReset && (
              <Button variant="outline" size="sm" onClick={onReset}>
                Back to setup
              </Button>
            )}
          </div>
        )}

        {stage1 && (
          <>
            {isSettled(data.status) || stage1.state === "not_applicable" ? (
              <Stage1View data={data} />
            ) : (
              <>
                <h2 className="text-lg font-semibold">
                  Compounds ({stage1.compounds?.length ?? 0})
                </h2>
                <ul className="text-hf-fg-2 list-disc pl-5 text-sm">
                  {stage1.compounds?.map((c, i) => (
                    <li key={i}>{c.canonical_name}</li>
                  ))}
                </ul>
              </>
            )}
            {/* ApprovalBar self-gates to the current stage, so stacked views show a single button. */}
            {(stage1 as { stale?: boolean }).stale && rerunFrom != null && (
              <StaleNotice analysisId={analysisId} fromStage={rerunFrom} />
            )}
            <ApprovalBar
              stage={1}
              status={data.status}
              currentStage={data.current_stage}
              disabled={(stage1.count ?? 0) === 0 || anyStale}
              disabledReason={
                anyStale
                  ? "Re-run the out-of-date step before continuing."
                  : "No compounds — add one to continue."
              }
              onApprove={() => advance.mutate()}
            />
          </>
        )}

        {Boolean(data.stage_results?.["2"]) && <Stage2View data={data} />}

        {Boolean(data.stage_results?.["3"]) && <Stage3View data={data} />}

        {Boolean(data.stage_results?.["4"]) && <Stage4View data={data} />}

        {Boolean(data.stage_results?.["5"]) && <Stage5View data={data} />}

        {Boolean(data.stage_results?.["6"]) && <Stage6View data={data} />}

        {Boolean(data.stage_results?.["7"]) && <Stage7View data={data} />}

        {Boolean(data.stage_results?.["8"]) && <Stage8View data={data} />}
      </section>
    </div>
  );
}
