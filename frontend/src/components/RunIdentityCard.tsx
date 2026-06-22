import type { AnalysisRead } from "@/api/types.gen";
import { formatRelative } from "@/lib/format";

// The run's identity in the sidebar: its custom name (never the UUID) + a quiet meta line.
// A SOLID card for contrast against the glass chrome sidebar.
export function RunIdentityCard({ data }: { data: AnalysisRead }) {
  const name = data.analysis_name?.trim() || "Untitled analysis";
  const created = data.created_at ? formatRelative(data.created_at) : null;
  return (
    <div className="border-hf-border bg-hf-surface rounded-[var(--radius-md)] border p-3">
      <p className="text-hf-fg-1 truncate font-medium" title={name}>
        {name}
      </p>
      <p className="text-hf-fg-4 mt-0.5 font-mono text-[0.65rem] tracking-wide uppercase">
        {data.mode}
        {created ? ` · started ${created}` : ""}
      </p>
    </div>
  );
}
