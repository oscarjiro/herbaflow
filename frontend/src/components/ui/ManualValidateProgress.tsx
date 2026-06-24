type ManualValidateKind = "compound" | "target";

export function ManualValidateProgress({
  kind,
  entryCount,
  completedCount = 0,
}: {
  kind: ManualValidateKind;
  entryCount: number;
  completedCount?: number;
}) {
  const total = Math.max(entryCount, 0);
  const completed = Math.min(Math.max(completedCount, 0), total);
  const percent = total === 0 ? 0 : Math.round((completed / total) * 100);
  const entryLabel = `${kind} ${entryCount === 1 ? "entry" : "entries"}`;
  const label = `Validating ${entryCount} ${entryLabel}`;
  const progressText = `${label}: ${completed} of ${entryCount} complete`;

  return (
    <div aria-busy="true" className="flex flex-col gap-2" role="status">
      <div className="progress-top flex items-baseline justify-between">
        <span className="text-hf-fg-1 text-[0.9rem] tabular-nums">
          Validating... {completed}/{entryCount}
        </span>
      </div>
      <div className="progress-bar w-full">
        <div
          aria-label={label}
          className="progress-fill"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={entryCount}
          aria-valuenow={completed}
          aria-valuetext={progressText}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
