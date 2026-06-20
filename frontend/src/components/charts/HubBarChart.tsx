/**
 * HubBarChart — horizontal bar chart of hub genes ranked by MCC.
 *
 * Receives a pre-mapped array of { gene_symbol, mcc } pairs (Stage7View maps its
 * full Hub[] down to this shape). Sorts descending by MCC so the top hub appears
 * at the top of the chart. Colors come from useChartColors() so the exported PNG
 * carries resolved hf-* values, never unresolved CSS variable references.
 */

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartColors } from "@/lib/chartTheme";

export type HubBarEntry = {
  gene_symbol: string;
  mcc: number;
};

type Props = {
  hubs: HubBarEntry[];
};

export function HubBarChart({ hubs }: Props) {
  const colors = useChartColors();

  // Sort descending so the highest-MCC hub appears at the top of the vertical axis.
  const sorted = [...hubs].sort((a, b) => b.mcc - a.mcc);

  const height = Math.max(240, sorted.length * 28);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={sorted} margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.border} horizontal={false} />
        <XAxis
          type="number"
          dataKey="mcc"
          tick={{ fill: colors.fg3, fontSize: 12 }}
          label={{
            value: "Maximal Clique Centrality (MCC)",
            position: "insideBottom",
            offset: -2,
            fill: colors.fg2,
            fontSize: 12,
          }}
          height={40}
        />
        <YAxis
          type="category"
          dataKey="gene_symbol"
          width={72}
          tick={{ fill: colors.fg2, fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            background: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: 6,
            fontSize: 13,
            color: colors.fg1,
          }}
          cursor={{ fill: colors.sageFaint }}
        />
        <Bar dataKey="mcc" fill={colors.sage} radius={[0, 3, 3, 0]} name="MCC" />
      </BarChart>
    </ResponsiveContainer>
  );
}
