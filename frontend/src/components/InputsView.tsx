import type { AnalysisRead } from "@/api/types.gen";
import { Eyebrow } from "@/components/ui/editorial";
import { useEntitySubjects } from "@/hooks/useEntitySubjects";

export function InputsView({ data }: { data: AnalysisRead }) {
  const { plant, disease } = useEntitySubjects(data);
  const rows: { label: string; value: string }[] = [
    { label: "Plant", value: plant },
    { label: "Disease", value: disease },
    { label: "Mode", value: data.mode ?? "guided" },
  ];
  return (
    <section className="flex flex-col gap-5">
      <header className="flex flex-col gap-1">
        <Eyebrow>00 · Inputs</Eyebrow>
        <h1 className="font-display text-hf-fg-1 text-3xl tracking-tight">Inputs</h1>
      </header>
      <dl className="border-hf-border bg-hf-surface divide-hf-border divide-y rounded-[var(--radius-lg)] border">
        {rows.map((r) => (
          <div key={r.label} className="grid grid-cols-[8rem_1fr] gap-3 p-4">
            <dt className="text-hf-fg-4 font-mono text-xs tracking-wide uppercase">{r.label}</dt>
            <dd className="text-hf-fg-1 text-sm">{r.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
