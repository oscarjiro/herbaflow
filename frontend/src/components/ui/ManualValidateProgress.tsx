type ManualValidateKind = "compound" | "target";

/**
 * Honest indeterminate busy indicator shown while /compounds/validate or
 * /targets/validate is in flight. Shows the distinct entry count so the
 * user knows what is being sent, with no fake 0/N fraction (the endpoint
 * returns one final response, not per-item progress).
 */
export function ManualValidateProgress({
  kind,
  entryCount,
}: {
  kind: ManualValidateKind;
  entryCount: number;
}) {
  const label = `Validating ${entryCount} ${kind} ${entryCount === 1 ? "entry" : "entries"}…`;

  return (
    <div aria-busy="true" role="status" className="flex items-center gap-2 text-sm">
      <span className="text-hf-fg-1 tabular-nums">{label}</span>
    </div>
  );
}
