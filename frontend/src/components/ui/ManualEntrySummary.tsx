import { Button } from "@/components/ui/button";

export function nonEmptyLineCount(value: string): number {
  return value.split("\n").filter((l) => l.trim().length > 0).length;
}

// One shared result-summary line for every manual-entry surface: at-a-glance valid / invalid /
// duplicate counts + the visible cap + Clear. Per-line errors are rendered separately by
// FailedInputList; this is the roll-up so neither box hand-rolls its own.
export function ManualEntrySummary({
  validCount,
  invalidCount,
  duplicateCount,
  current,
  max,
  onClear,
}: {
  validCount: number;
  invalidCount: number;
  duplicateCount: number;
  current: number;
  max: number;
  onClear?: () => void;
}) {
  return (
    <div className="text-hf-fg-3 flex flex-wrap items-center justify-between gap-2 text-sm">
      <span className="font-mono text-xs">
        <span className="text-hf-fg-1">{validCount}</span> valid ·{" "}
        <span className={invalidCount > 0 ? "text-hf-danger" : ""}>{invalidCount}</span> invalid ·{" "}
        <span>{duplicateCount}</span> duplicates
      </span>
      <span className="flex items-center gap-3">
        <span className="text-hf-fg-4 font-mono text-xs">
          {current.toLocaleString()} / {max.toLocaleString()}
        </span>
        {onClear && (
          <Button type="button" variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
        )}
      </span>
    </div>
  );
}
