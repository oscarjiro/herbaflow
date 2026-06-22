import { createFileRoute, Navigate } from "@tanstack/react-router";
import { useAnalysisStatus } from "@/hooks/useAnalysisStatus";
import { furthestReachedSlug } from "@/lib/stageRoutes";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/analysis/$id/")({
  component: function RunIndex() {
    const { id } = Route.useParams();
    const { data } = useAnalysisStatus(id);
    if (!data) return <Skeleton className="h-7 w-64" />;
    return (
      <Navigate
        to="/analysis/$id/$stage"
        params={{ id, stage: furthestReachedSlug(data) }}
        replace
      />
    );
  },
});
