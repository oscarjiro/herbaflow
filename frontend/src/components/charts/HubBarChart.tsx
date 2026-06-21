/**
 * HubBarChart — tabbed Plotly horizontal bars of hub genes.
 *
 * One tab per metric: MCC (the ranker, default) plus the four reported
 * centralities (degree/betweenness/closeness/eigenvector). NO composite tab —
 * MCC is the sole ranker (Methodology Lock §7). The active tab's chart is what
 * ChartFrame's Download PNG exports.
 */
import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PlotlyChart } from "./PlotlyChart";
import { useChartColors } from "@/lib/chartTheme";
import {
  buildCentralityBarTraces,
  CENTRALITY_TABS,
  type CentralityHub,
  type CentralityMetric,
} from "@/lib/centralityBars";

type Props = {
  hubs: CentralityHub[];
  onGraphDiv?: (gd: HTMLElement | null) => void;
};

export function HubBarChart({ hubs, onGraphDiv }: Props) {
  const colors = useChartColors();
  const [metric, setMetric] = useState<CentralityMetric>("mcc");
  const height = Math.max(280, hubs.length * 28);
  const label = CENTRALITY_TABS.find((t) => t.key === metric)?.label ?? "MCC";

  return (
    <div className="flex flex-col gap-3">
      <Tabs value={metric} onValueChange={(v) => setMetric(v as CentralityMetric)}>
        <TabsList>
          {CENTRALITY_TABS.map((t) => (
            <TabsTrigger key={t.key} value={t.key}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <PlotlyChart
        data={buildCentralityBarTraces(hubs, metric, colors.sage)}
        layout={{ xaxis: { title: { text: label } }, margin: { l: 80, r: 16, t: 8, b: 40 } }}
        height={height}
        onGraphDiv={onGraphDiv}
      />
    </div>
  );
}
