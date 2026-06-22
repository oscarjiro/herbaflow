import { useQuery } from "@tanstack/react-query";
import { Navigate, useNavigate } from "@tanstack/react-router";
import { healthOptions } from "@/api/@tanstack/react-query.gen";
import { getActiveRunId, setActiveRunId } from "@/lib/activeRun";
import { ServiceUnavailable } from "@/components/ServiceUnavailable";
import { SetupView } from "@/components/SetupView";
import { Skeleton } from "@/components/ui/skeleton";
import { SHELL_MODE } from "@/lib/shellMode";
import { SetupShell } from "@/components/setup/SetupShell";

export function AnalysisGate() {
  const navigate = useNavigate();
  // Probe the backend/DB before deciding; retry once so a transient blip doesn't show the error page.
  const health = useQuery({ ...healthOptions(), retry: 1, staleTime: 0, gcTime: 0 });

  if (health.isPending) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-3 px-4 py-24" aria-label="Loading">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (health.isError) {
    return <ServiceUnavailable onRetry={() => void health.refetch()} />;
  }

  const activeId = getActiveRunId();
  if (activeId) {
    return <Navigate to="/analysis/$id" params={{ id: activeId }} replace />;
  }

  const setup = (
    <SetupView
      onCreated={(id) => {
        setActiveRunId(id);
        navigate({ to: "/analysis/$id", params: { id } });
      }}
    />
  );
  return SHELL_MODE === "unified" ? <SetupShell>{setup}</SetupShell> : setup;
}
