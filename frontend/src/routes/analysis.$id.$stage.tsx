import { createFileRoute, Navigate } from "@tanstack/react-router";
import { useAnalysisStatus } from "@/hooks/useAnalysisStatus";
import {
  isValidStageSlug,
  isSlugApplicable,
  isSlugReached,
  furthestReachedSlug,
} from "@/lib/stageRoutes";
import { RunStageContent } from "@/components/RunStageContent";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/analysis/$id/$stage")({
  component: function RunStage() {
    const { id, stage } = Route.useParams();
    const { data } = useAnalysisStatus(id);
    if (!data) return <Skeleton className="h-7 w-64" />;
    if (!isValidStageSlug(stage) || !isSlugApplicable(stage, data) || !isSlugReached(stage, data)) {
      return (
        <Navigate
          to="/analysis/$id/$stage"
          params={{ id, stage: furthestReachedSlug(data) }}
          replace
        />
      );
    }
    return <RunStageContent analysisId={id} slug={stage} />;
  },
});
