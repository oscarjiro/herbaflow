import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  listAnalysesOptions,
  listDiseasesOptions,
  listPlantsOptions,
} from "../api/@tanstack/react-query.gen";
import { deriveSubjects } from "../hooks/useEntitySubjects";
import { formatRunStatus } from "../lib/runStatus";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export function RecentRuns() {
  const { data: runs, isLoading: runsLoading } = useQuery(listAnalysesOptions());
  const { data: plants } = useQuery(listPlantsOptions());
  const { data: diseases } = useQuery(listDiseasesOptions());

  if (runsLoading) {
    return (
      <div className="flex flex-col gap-2" aria-label="Loading recent runs">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-14 w-full rounded-[var(--radius-3)]" />
        ))}
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return <p className="text-hf-fg-3 text-sm">No runs yet.</p>;
  }

  return (
    <ul className="flex flex-col gap-2" aria-label="Recent runs">
      {runs.map((run) => {
        const { plant, disease } = deriveSubjects(
          run.parameters as Record<string, unknown> | undefined,
          run.disease_id,
          plants,
          diseases,
        );
        const dateStr = run.created_at ? new Date(run.created_at).toLocaleDateString() : null;

        return (
          <li key={run.analysis_id}>
            <Link
              to="/analysis/$id"
              params={{ id: run.analysis_id }}
              className="border-hf-border bg-hf-surface hover:bg-hf-surface-2 flex items-center justify-between gap-3 rounded-[var(--radius-3)] border px-4 py-3 transition-colors"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="text-hf-fg-1 truncate text-sm font-medium">
                  {run.analysis_name ?? run.analysis_id}
                </span>
                <span className="text-hf-fg-3 truncate text-xs">
                  {plant} · {disease}
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <Badge variant="outline" className="capitalize">
                  {formatRunStatus(run.status)}
                </Badge>
                {dateStr && <span className="text-hf-fg-3 text-xs">{dateStr}</span>}
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
