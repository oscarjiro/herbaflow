import type { Data } from "plotly.js";

export type CentralityMetric = "mcc" | "degree" | "betweenness" | "closeness" | "eigenvector";
export type CentralityHub = { gene_symbol: string } & Record<CentralityMetric, number>;

// MCC first (the sole ranker); the four reported centralities follow.
// NO composite/overall tab — MCC is the exclusive ranking criterion (Methodology Lock §7).
export const CENTRALITY_TABS: { key: CentralityMetric; label: string }[] = [
  { key: "mcc", label: "MCC" },
  { key: "degree", label: "Degree" },
  { key: "betweenness", label: "Betweenness" },
  { key: "closeness", label: "Closeness" },
  { key: "eigenvector", label: "Eigenvector" },
];

/**
 * One horizontal bar trace for the chosen metric.
 *
 * Plotly renders the first y-axis entry at the bottom of the chart. To put the
 * highest value at the top, we sort descending then reverse to ascending — the
 * ascending array feeds Plotly, which stacks upward so the highest bar lands at
 * the top of the visible chart.
 */
export function buildCentralityBarTraces(
  hubs: CentralityHub[],
  metric: CentralityMetric,
  barColor: string,
): Data[] {
  const sortedDesc = [...hubs].sort((a, b) => b[metric] - a[metric]);
  const ascForPlot = [...sortedDesc].reverse();
  return [
    {
      type: "bar",
      orientation: "h",
      x: ascForPlot.map((h) => h[metric]),
      y: ascForPlot.map((h) => h.gene_symbol),
      marker: { color: barColor },
      hovertemplate: "%{y}: %{x}<extra></extra>",
    },
  ];
}
