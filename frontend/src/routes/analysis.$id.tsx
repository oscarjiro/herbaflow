import { createFileRoute, Outlet, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect } from "react";
import { toast } from "sonner";
import { useAnalysisStatus } from "@/hooks/useAnalysisStatus";
import { clearActiveRunId, getActiveRunId, setActiveRunId } from "@/lib/activeRun";
import { RunSidebar } from "@/components/RunSidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { humanizeProblem, isHardDown, type Problem } from "@/lib/problem";

export const Route = createFileRoute("/analysis/$id")({
  component: RunShell,
});

function RunShell() {
  const { id } = useParams({ from: "/analysis/$id" });
  const navigate = useNavigate();
  const { data, isError, error } = useAnalysisStatus(id);

  // Leave the run shell whenever the 1s poll can't yield a usable run. Both cases
  // bail to /analysis so this page never sits on a dead/unreachable backend looping
  // its outage screen against the loading state:
  //  - 404 (run deleted/expired) or 422 (malformed id, e.g. a stale "null"): the run
  //    is gone, so clear the cached active-run id and return to setup with a notice.
  //  - hard-down (transport failure / 402 / 503): the backend is unreachable. The
  //    health-gated /analysis entry owns the single service-unavailable screen, so
  //    hand off to it instead of flickering one here. Keep the active-run id so the
  //    run resumes here once the backend is reachable again.
  // The poll throws the RFC 9457 problem body, which carries the HTTP status.
  useEffect(() => {
    if (!isError) return;
    const status = (error as Problem)?.status;
    if (status === 404 || status === 422) {
      clearActiveRunId();
      toast.error("That analysis is no longer available.");
      navigate({ to: "/analysis" });
    } else if (isHardDown(error as Problem)) {
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
    // A genuine transient error (e.g. a 500) keeps retrying inline. Hard-down and the
    // self-heal statuses (404/422) are handled by the redirect effect above, so they
    // fall through to the neutral skeleton for the frame before it navigates away.
    if (isError && !isHardDown(error as Problem)) {
      const status = (error as Problem)?.status;
      if (status !== 404 && status !== 422) {
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
