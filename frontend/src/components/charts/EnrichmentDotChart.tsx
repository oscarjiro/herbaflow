/**
 * EnrichmentDotChart — tabbed Plotly bubble plot of pathway enrichment.
 *
 * One tab per annotation source present (GO:BP / GO:MF / GO:CC / KEGG / REAC /
 * WP), labeled via ENRICHMENT_SOURCE_LABELS. Each bubble: x = -log10 p,
 * y = term, size = gene count, color = -log10 p on a Viridis colorbar. The
 * active tab is what ChartFrame's Download PNG exports.
 */
import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PlotlyChart } from "./PlotlyChart";
import {
  buildEnrichmentBubble,
  groupTermsBySource,
  type EnrichmentDotEntry,
} from "@/lib/enrichmentBubble";

export type { EnrichmentDotEntry };

type Props = {
  terms: EnrichmentDotEntry[];
  onGraphDiv?: (gd: HTMLElement | null) => void;
};

export function EnrichmentDotChart({ terms, onGraphDiv }: Props) {
  const groups = groupTermsBySource(terms);
  const [active, setActive] = useState(groups[0]?.source ?? "");
  if (groups.length === 0) return null;
  // groups is non-empty at this point; fallback to first group when active key
  // is not found (e.g. immediately after state initialization on an empty string).
  const current = groups.find((g) => g.source === active) ?? groups[0]!;
  const height = Math.max(280, current.terms.slice(0, 20).length * 26);

  return (
    <div className="flex flex-col gap-3">
      <Tabs value={current.source} onValueChange={setActive}>
        <TabsList>
          {groups.map((g) => (
            <TabsTrigger key={g.source} value={g.source}>
              {g.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <PlotlyChart
        data={buildEnrichmentBubble(current.terms)}
        layout={{
          xaxis: { title: { text: "Significance (-log10 p-value)" } },
          yaxis: { automargin: true },
          margin: { l: 8, r: 16, t: 8, b: 48 },
        }}
        height={height}
        onGraphDiv={onGraphDiv}
      />
    </div>
  );
}
