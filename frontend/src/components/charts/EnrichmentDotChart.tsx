/**
 * EnrichmentDotChart — scatter/dot plot for pathway enrichment results.
 *
 * Each dot represents one enriched term. X-axis encodes significance
 * (-log10 corrected p-value); dot size encodes intersection size (overlap
 * between the query gene set and the term). Terms are colored by source
 * database. The top 20 most-significant terms are shown to keep the chart
 * readable regardless of how many terms the run returns.
 *
 * Self-contained; wrap in ChartFrame for the titled card + Download PNG.
 */

import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { ENRICHMENT_SOURCE_LABELS } from "@/contract/labels";
import { useChartColors } from "@/lib/chartTheme";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EnrichmentDotEntry = {
  source: string;
  name: string;
  p_value: number;
  intersection_size: number;
};

type PlottedPoint = {
  source: string;
  name: string;
  negLogP: number;
  intersection_size: number;
};

type Props = {
  terms: EnrichmentDotEntry[];
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_TERMS = 20;

// Source → color key in ChartColors. Keys are the canonical g:Profiler source
// strings (the shared contract enrichment `sources` enum), e.g. "GO:BP" — the
// same values the backend persists in each term's `source`.
const SOURCE_COLOR_KEY: Record<string, keyof ReturnType<typeof useChartColors>> = {
  "GO:BP": "sage",
  "GO:MF": "terracotta",
  "GO:CC": "info",
  KEGG: "warning",
  REAC: "sageDeep",
  WP: "success",
};

// Ordered list so legend order is deterministic
const SOURCE_ORDER = ["GO:BP", "GO:MF", "GO:CC", "KEGG", "REAC", "WP"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EnrichmentDotChart({ terms }: Props) {
  const colors = useChartColors();

  // Sort ascending by p_value (most significant first), cap at MAX_TERMS
  const top = [...terms].sort((a, b) => a.p_value - b.p_value).slice(0, MAX_TERMS);

  // Map to plottable points, clamping p_value to avoid log10(0) = -Infinity
  const points: PlottedPoint[] = top.map((t) => ({
    source: t.source,
    name: t.name,
    negLogP: -Math.log10(Math.max(t.p_value, 1e-300)),
    intersection_size: t.intersection_size,
  }));

  // Group by source for separate Scatter series (one per source present)
  const sourcesPresent = SOURCE_ORDER.filter((s) => points.some((p) => p.source === s));
  const bySource: Record<string, PlottedPoint[]> = {};
  for (const s of sourcesPresent) {
    bySource[s] = points.filter((p) => p.source === s);
  }

  const n = points.length;
  const height = Math.max(280, n * 26);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 8, right: 24, bottom: 40, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
        <XAxis
          type="number"
          dataKey="negLogP"
          name="Significance"
          tick={{ fill: colors.fg3, fontSize: 12 }}
          label={{
            value: "Significance (-log10 p-value)",
            position: "insideBottom",
            offset: -24,
            fill: colors.fg2,
            fontSize: 12,
          }}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={180}
          tick={{ fill: colors.fg2, fontSize: 11 }}
        />
        <ZAxis
          type="number"
          dataKey="intersection_size"
          name="Intersection size"
          range={[40, 400]}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          contentStyle={{
            background: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: 6,
            fontSize: 13,
            color: colors.fg1,
          }}
        />
        <Legend verticalAlign="top" height={36} />
        {sourcesPresent.map((source) => (
          <Scatter
            key={source}
            name={ENRICHMENT_SOURCE_LABELS[source] ?? source}
            data={bySource[source]}
            fill={colors[SOURCE_COLOR_KEY[source] ?? "sage"]}
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
