import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCtpGraphOptions } from "@/api/@tanstack/react-query.gen";
import type { AnalysisRead, GetCtpGraphResponse } from "@/api/types.gen";
import { buildCtpElements, buildCtpStylesheet, ctpConcentricLayout } from "@/lib/ctpGraph";
import { useChartColors } from "@/lib/chartTheme";
import { runHasCompounds } from "@/lib/entities";
import { useEntitySubjects } from "@/hooks/useEntitySubjects";
import { NetworkGraph } from "@/components/charts/NetworkGraph";
import { DownloadResults } from "@/components/DownloadResults";
import { Eyebrow, StatNumber } from "@/components/ui/editorial";
import { Skeleton } from "@/components/ui/skeleton";

export function FinalView({ analysisId, data }: { analysisId: string; data: AnalysisRead }) {
  const colors = useChartColors();
  const { plant, disease } = useEntitySubjects(data);
  const hasCompounds = runHasCompounds(data);

  const ctpEnabled = data.status === "complete" && hasCompounds;
  const ctpQuery = useQuery({
    ...getCtpGraphOptions({ path: { analysis_id: analysisId } }),
    enabled: ctpEnabled,
  });

  const ctpGraph = (ctpQuery.data as GetCtpGraphResponse | undefined) ?? null;
  const ctpElements = useMemo(() => (ctpGraph ? buildCtpElements(ctpGraph) : []), [ctpGraph]);
  const ctpStylesheet = useMemo(() => buildCtpStylesheet(colors), [colors]);

  const summary: { label: string; value: number | string }[] = [
    { label: "Plant", value: plant },
    { label: "Disease", value: disease },
    { label: "Hub genes", value: (data.stage_results?.["7"] as { count?: number })?.count ?? 0 },
    {
      label: "Enriched terms",
      value: (data.stage_results?.["8"] as { count?: number })?.count ?? 0,
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <Eyebrow>Results</Eyebrow>
        <h1 className="font-display text-hf-fg-1 text-3xl tracking-tight">Final results</h1>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {summary.map((s) => (
          <div
            key={s.label}
            className="border-hf-border bg-hf-surface rounded-[var(--radius-lg)] border p-4"
          >
            <p className="text-hf-fg-4 font-mono text-xs tracking-wide uppercase">{s.label}</p>
            <p className="font-display text-hf-fg-1 mt-1 text-2xl">
              {typeof s.value === "number" ? <StatNumber>{s.value}</StatNumber> : s.value}
            </p>
          </div>
        ))}
      </div>

      {ctpEnabled &&
        (ctpQuery.isPending ? (
          <Skeleton className="h-[420px] w-full" />
        ) : ctpGraph && ctpGraph.nodes.length > 0 ? (
          <NetworkGraph
            title="Compound, target and pathway network"
            filename="ctp_network.png"
            elements={ctpElements}
            stylesheet={ctpStylesheet}
            layout={ctpConcentricLayout()}
            nodeTooltip={(d) =>
              d["type"] === "target"
                ? `Target: ${String(d["label"] ?? "")}`
                : `${String(d["type"] ?? "")}: ${String(d["label"] ?? "")}`
            }
            legend={
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                <span className="text-hf-fg-2 font-medium">Legend:</span>
                <span className="flex items-center gap-1.5">
                  <span className="bg-hf-warning inline-block h-3 w-3 rounded-sm" />
                  <span className="text-hf-fg-2">Compound</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="bg-hf-info inline-block h-3 w-3 rounded-full" />
                  <span className="text-hf-fg-2">Target</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="bg-hf-sage-deep inline-block h-3 w-3 rounded-full" />
                  <span className="text-hf-fg-2">Hub target</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="bg-hf-danger inline-block h-3 w-3 rounded-sm" />
                  <span className="text-hf-fg-2">Pathway / Disease</span>
                </span>
              </div>
            }
          />
        ) : null)}

      <DownloadResults status={data.status} analysisId={analysisId} run={data} />
    </section>
  );
}
