import { describe, expect, it } from "vitest";
import { groupTermsBySource, buildEnrichmentBubble } from "./enrichmentBubble";

const terms = [
  { source: "GO:BP", name: "apoptotic process", p_value: 1e-8, intersection_size: 12 },
  { source: "GO:BP", name: "inflammatory response", p_value: 1e-4, intersection_size: 5 },
  { source: "KEGG", name: "PI3K-Akt signaling", p_value: 1e-6, intersection_size: 9 },
];

describe("enrichmentBubble", () => {
  it("groups by real enum source keys, labeled, only present categories", () => {
    const groups = groupTermsBySource(terms);
    expect(groups.map((g) => g.source)).toEqual(["GO:BP", "KEGG"]);
    expect(groups[0]!.label).toBe("Biological Process");
    expect(groups.find((g) => g.source === "GO:MF")).toBeUndefined();
  });
  it("encodes x=-log10p, size=intersection, color=-log10p with a viridis colorbar", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [trace] = buildEnrichmentBubble(terms.filter((t) => t.source === "GO:BP")) as any[];
    expect(trace.mode).toBe("markers");
    expect(trace.x[0]).toBeCloseTo(8); // -log10(1e-8)
    expect(trace.marker.size).toEqual([12, 5]);
    expect(trace.marker.colorscale).toBe("Viridis");
    expect(trace.marker.showscale).toBe(true);
  });
});
