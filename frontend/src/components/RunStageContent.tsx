import { useMutation, useQueryClient } from "@tanstack/react-query";
import { advanceAnalysis } from "@/api/sdk.gen";
import { useAnalysisStatus } from "@/hooks/useAnalysisStatus";
import { notifyError } from "@/lib/toast";
import type { Problem } from "@/lib/problem";
import { stageLabel } from "@/contract/labels";
import { slugToStage, type StageSlug } from "@/lib/stageRoutes";
import { StageView } from "@/components/stages/StageView";
import { Stage1View } from "@/components/stages/Stage1View";
import { Stage2View } from "@/components/stages/Stage2View";
import { Stage3View } from "@/components/stages/Stage3View";
import { Stage4View } from "@/components/stages/Stage4View";
import { Stage5View } from "@/components/stages/Stage5View";
import { Stage6View } from "@/components/stages/Stage6View";
import { Stage7View } from "@/components/stages/Stage7View";
import { Stage8View } from "@/components/stages/Stage8View";
import { FinalView } from "@/components/FinalView";
import { InputsView } from "@/components/InputsView";

const STAGE_VIEW = {
  1: Stage1View,
  2: Stage2View,
  3: Stage3View,
  4: Stage4View,
  5: Stage5View,
  6: Stage6View,
  7: Stage7View,
  8: Stage8View,
} as const;

export function RunStageContent({ analysisId, slug }: { analysisId: string; slug: StageSlug }) {
  const { data } = useAnalysisStatus(analysisId);
  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: async () => advanceAnalysis({ path: { analysis_id: analysisId } }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (e) => notifyError(e as Problem),
  });

  if (!data) return null;
  if (slug === "final") return <FinalView analysisId={analysisId} data={data} />;
  if (slug === "inputs") return <InputsView data={data} />;

  const n = slugToStage(slug);
  if (n == null) return null;
  const View = STAGE_VIEW[n as keyof typeof STAGE_VIEW];
  if (!View) return null;
  const kickerNum = String(n).padStart(2, "0");
  const title = stageLabel(n);

  return (
    <StageView
      data={data}
      stage={n}
      title={title}
      kicker={`${kickerNum} · ${title}`}
      onApprove={() => advance.mutate()}
      approvePending={advance.isPending}
    >
      <View data={data} />
    </StageView>
  );
}
