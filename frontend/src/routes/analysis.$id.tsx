import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { RunView } from "@/components/RunView";

export const Route = createFileRoute("/analysis/$id")({
  component: function AnalysisRun() {
    const { id } = Route.useParams();
    const navigate = useNavigate();
    return <RunView analysisId={id} onReset={() => navigate({ to: "/analysis" })} />;
  },
});
