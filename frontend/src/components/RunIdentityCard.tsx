import type { AnalysisRead } from "@/api/types.gen";
import { formatRelative } from "@/lib/format";

// Run-card shown in the sidebar chrome — solid surface card for contrast against glass.
// Layout: label (mono, tiny, uppercase) → name (serif display) → meta (mode · time).
export function RunIdentityCard({ data }: { data: AnalysisRead }) {
  const name = data.analysis_name?.trim() || "Untitled analysis";
  const created = data.created_at ? formatRelative(data.created_at) : null;
  const mode = data.mode ? data.mode.charAt(0).toUpperCase() + data.mode.slice(1) : null;

  return (
    <div className="run-card">
      <p className="rc-label">Active run</p>
      <p className="rc-name" title={name}>
        {name}
      </p>
      <p className="rc-meta">
        {mode}
        {created ? ` · started ${created}` : ""}
      </p>
    </div>
  );
}
