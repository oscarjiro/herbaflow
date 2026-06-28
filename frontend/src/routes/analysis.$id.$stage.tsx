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
    if (!data)
      return (
        <div className="flex flex-col gap-5" aria-busy="true" aria-label="Loading step">
          <Skeleton className="h-9 w-72" />
          <div className="flex flex-col gap-3">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-5/6" />
            <Skeleton className="h-6 w-2/3" />
          </div>
        </div>
      );
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
