import { createFileRoute, Outlet, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect } from "react";
import { toast } from "sonner";
import { useAnalysisStatus } from "@/hooks/useAnalysisStatus";
import { clearActiveRunId, getActiveRunId, setActiveRunId } from "@/lib/activeRun";
import { RunSidebar } from "@/components/RunSidebar";
import { ServiceUnavailable } from "@/components/ServiceUnavailable";
import { Skeleton } from "@/components/ui/skeleton";
import { humanizeProblem, isServiceOutage, type Problem } from "@/lib/problem";

export const Route = createFileRoute("/analysis/$id")({
  component: RunShell,
});

function RunShell() {
  const { id } = useParams({ from: "/analysis/$id" });
  const navigate = useNavigate();
  const { data, isError, error, refetch } = useAnalysisStatus(id);

  // Self-heal an unusable cached run: a 404 means the run was deleted or expired;
  // a 422 means the id is malformed (e.g. a stale "null"), which would otherwise
  // retry every second forever. The poll throws the RFC 9457 problem body, which
  // carries the HTTP status. Outage statuses (402/503) are NOT self-healed here —
  // they surface the service-unavailable screen below so the run can resume.
  useEffect(() => {
    const status = (error as Problem)?.status;
    if (isError && (status === 404 || status === 422)) {
      clearActiveRunId();
      toast.error("That analysis is no longer available.");
      navigate({ to: "/analysis" });
    }
  }, [isError, error, navigate]);

  // Deep-linking straight to a valid run caches it so /analysis later resumes here.
  useEffect(() => {
    if (data && getActiveRunId() !== id) {
      setActiveRunId(id);
    }
  }, [data, id]);

  if (!data) {
    if (isError && isServiceOutage(error as Problem)) {
      return <ServiceUnavailable onRetry={() => void refetch()} />;
    }
    if (isError) {
      return (
        <div
          role="alert"
          className="border-hf-danger/30 bg-hf-danger-soft/20 mx-auto max-w-lg rounded-[var(--radius-3)] border p-6 text-sm"
        >
          <p className="text-hf-fg-1 font-medium">Could not load analysis status</p>
          <p className="text-hf-fg-2 mt-1">{humanizeProblem(error as Problem)} Retrying...</p>
        </div>
      );
    }
    return (
      <div className="flex flex-col gap-3 p-6">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-48" />
      </div>
    );
  }

  return (
    <div className="lg:flex">
      <RunSidebar data={data} analysisId={id} onExit={() => navigate({ to: "/analysis" })} />
      <main className="mx-auto flex max-w-[920px] min-w-0 flex-col gap-6 p-6 lg:flex-1">
        <Outlet />
      </main>
    </div>
  );
}
