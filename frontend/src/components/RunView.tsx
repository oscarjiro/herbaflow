import { useMutation, useQueryClient } from "@tanstack/react-query";
import { advanceAnalysis } from "../api/sdk.gen";
import { useAnalysisStatus } from "../hooks/useAnalysisStatus";

export function RunView({ analysisId }: { analysisId: string }) {
  const { data } = useAnalysisStatus(analysisId);
  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: async () => advanceAnalysis({ path: { analysis_id: analysisId } }),
    onSuccess: () => qc.invalidateQueries(),
  });

  if (!data) return <p>Loading…</p>;

  const stage1 = data.stage_results?.["1"] as
    | { compounds?: { canonical_name?: string }[] }
    | undefined;

  return (
    <section>
      <h1>Run {analysisId}</h1>
      <p>Status: {data.status}</p>
      {data.status === "failed" && <p role="alert">{data.error_message}</p>}
      {data.status === "stage_1_awaiting_approval" && (
        <button onClick={() => advance.mutate()}>Approve and continue</button>
      )}
      {stage1 && (
        <>
          <h2>Compounds ({stage1.compounds?.length ?? 0})</h2>
          <ul>
            {stage1.compounds?.map((c, i) => (
              <li key={i}>{c.canonical_name}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
