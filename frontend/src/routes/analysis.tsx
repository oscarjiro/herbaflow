import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { SetupView } from "@/components/SetupView";

export const Route = createFileRoute("/analysis")({
  component: function AnalysisSetup() {
    const navigate = useNavigate();
    return <SetupView onCreated={(id) => navigate({ to: "/analysis/$id", params: { id } })} />;
  },
});
