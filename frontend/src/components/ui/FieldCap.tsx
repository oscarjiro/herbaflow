export function FieldCap({ current, max, unit }: { current: number; max: number; unit?: string }) {
  return (
    <span data-slot="field-cap" className="text-hf-fg-4 font-mono text-xs tabular-nums">
      {current.toLocaleString()} / {max.toLocaleString()}
      {unit ? ` ${unit}` : ""}
    </span>
  );
}
