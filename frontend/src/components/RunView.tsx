import { useMutation, useQueryClient } from "@tanstack/react-query";
import { advanceAnalysis } from "../api/sdk.gen";
import { useAnalysisStatus } from "../hooks/useAnalysisStatus";
import { useEntitySubjects } from "../hooks/useEntitySubjects";
import { useStaleState } from "../hooks/useStaleState";
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

  if (!data) return <p>Loading…</p>;

  // stage1 is still used below for the inline (unsettled) fallback rendering and ApprovalBar.
  const stage1 = data.stage_results?.["1"] as Stage1Data | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  return (
    <section>
      <h1>Run {analysisId}</h1>
      <p>Status: {data.status}</p>
      <p className="run-header__subjects">
        Plant: {plantDisplay} · Disease: {diseaseDisplay}
      </p>
      {data.status === "failed" && (
        <div role="alert">
          <p>{data.error_message}</p>
          {onReset && (
            <button className="hf-btn" onClick={onReset}>
              Back to setup
            </button>
          )}
        </div>
      )}

      {stage1 && (
        <>
          {isSettled(data.status) || stage1.state === "not_applicable" ? (
            <Stage1View data={data} />
          ) : (
            <>
              <h2>Compounds ({stage1.compounds?.length ?? 0})</h2>
              <ul>
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
  );
}
