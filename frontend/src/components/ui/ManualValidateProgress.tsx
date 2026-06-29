import type { ChunkProgress } from "@/hooks/useChunkedValidate";

type ManualValidateKind = "compound" | "target";

/**
 * Busy indicator shown while /compounds/validate or /targets/validate is in
 * flight.
 *
 * When `progress` is supplied (the batched validate path), it renders a real
 * determinate "Validating X of N…" bar — honest progress for large pastes that
 * resolve over several seconds. Without `progress` it falls back to an
 * indeterminate label showing the distinct entry count.
 */
export function ManualValidateProgress({
  kind,
  entryCount,
  progress,
}: {
  kind: ManualValidateKind;
  entryCount: number;
  progress?: ChunkProgress | null;
}) {
  const noun = (n: number) => `${kind} ${n === 1 ? "entry" : "entries"}`;

  if (progress) {
    const { done, total } = progress;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const label = `Validating ${done} of ${total} ${noun(total)}…`;
    return (
      <div
        aria-busy="true"
        role="status"
        aria-label={label}
        className="flex flex-col gap-1 text-sm"
      >
        <span className="text-hf-fg-1 tabular-nums">{label}</span>
        <div className="bg-hf-border h-1 w-full overflow-hidden rounded-full">
          <div
            role="progressbar"
            aria-valuenow={done}
            aria-valuemin={0}
            aria-valuemax={total}
            className="bg-hf-fg-2 h-full rounded-full transition-[width] duration-300 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    );
  }

  const label = `Validating ${entryCount} ${noun(entryCount)}…`;
  return (
    <div aria-busy="true" role="status" className="flex items-center gap-2 text-sm">
      <span className="text-hf-fg-1 tabular-nums">{label}</span>
    </div>
  );
}
