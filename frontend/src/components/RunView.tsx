import { useMutation, useQueryClient } from "@tanstack/react-query";
import { advanceAnalysis } from "../api/sdk.gen";
import { useAnalysisStatus } from "../hooks/useAnalysisStatus";
import { ApprovalBar } from "./stages/ApprovalBar";
import { Stage1View } from "./stages/Stage1View";
import { Stage2View } from "./stages/Stage2View";

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

export function RunView({ analysisId }: { analysisId: string }) {
  const { data } = useAnalysisStatus(analysisId);
  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: async () => advanceAnalysis({ path: { analysis_id: analysisId } }),
    onSuccess: () => qc.invalidateQueries(),
  });

  if (!data) return <p>Loading…</p>;

  const stage1 = data.stage_results?.["1"] as Stage1Data | undefined;

  return (
    <section>
      <h1>Run {analysisId}</h1>
      <p>Status: {data.status}</p>
      {data.status === "failed" && <p role="alert">{data.error_message}</p>}

      {stage1 && (
        <>
          {isSettled(data.status) ? (
            <Stage1View analysisId={analysisId} stage1={stage1} />
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
          <ApprovalBar
            status={data.status}
            currentStage={data.current_stage}
            onApprove={() => advance.mutate()}
          />
        </>
      )}

      {Boolean(data.stage_results?.["2"]) && <Stage2View data={data} />}
    </section>
  );
}
