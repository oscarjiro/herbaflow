import type { Data } from "plotly.js";
import { ENRICHMENT_SOURCE_LABELS } from "@/contract/labels";

export type EnrichmentDotEntry = {
  source: string;
  name: string;
  p_value: number;
  intersection_size: number;
};

// Deterministic enum order; only categories actually present are returned.
const SOURCE_ORDER = ["GO:BP", "GO:MF", "GO:CC", "KEGG", "REAC", "WP"];

export function groupTermsBySource(
  terms: EnrichmentDotEntry[],
): { source: string; label: string; terms: EnrichmentDotEntry[] }[] {
  return SOURCE_ORDER.map((source) => ({
    source,
    label: ENRICHMENT_SOURCE_LABELS[source] ?? source,
    terms: terms.filter((t) => t.source === source),
  })).filter((g) => g.terms.length > 0);
}

const MAX_TERMS = 20;
const negLog10 = (p: number) => -Math.log10(Math.max(p, 1e-300));

/**
 * Bubble trace for one category: x = significance (-log10 adjusted p),
 * y = term name, marker size = intersection (gene) count, marker color =
 * significance on a continuous Viridis colorbar (clusterProfiler convention;
 * color and size encode different dimensions).
 */
export function buildEnrichmentBubble(terms: EnrichmentDotEntry[]): Data[] {
  const top = [...terms].sort((a, b) => a.p_value - b.p_value).slice(0, MAX_TERMS);
  const x = top.map((t) => negLog10(t.p_value));
  return [
    {
      type: "scatter",
      mode: "markers",
      x,
      y: top.map((t) => t.name),
      text: top.map((t) => `${t.name}<br>genes: ${t.intersection_size}`),
      hovertemplate: "%{text}<br>-log10 p: %{x:.2f}<extra></extra>",
      marker: {
        size: top.map((t) => t.intersection_size),
        sizemode: "area",
        sizeref: Math.max(...top.map((t) => t.intersection_size), 1) / 400,
        sizemin: 6,
        color: x,
        colorscale: "Viridis",
        showscale: true,
        colorbar: { title: { text: "-log10 p" } },
      },
    },
  ];
}
