import { buildCentralityBarTraces, CENTRALITY_TABS } from "./centralityBars";

const hubs = [
  { gene_symbol: "TP53", mcc: 120, degree: 9, betweenness: 0.4, closeness: 0.7, eigenvector: 0.9 },
  { gene_symbol: "AKT1", mcc: 80, degree: 12, betweenness: 0.2, closeness: 0.6, eigenvector: 0.5 },
];

describe("centralityBars", () => {
  it("offers MCC first and never a composite/overall tab", () => {
    expect(CENTRALITY_TABS[0]!.key).toBe("mcc");
    expect(CENTRALITY_TABS.map((t) => t.key)).toEqual([
      "mcc",
      "degree",
      "betweenness",
      "closeness",
      "eigenvector",
    ]);
    const keys = CENTRALITY_TABS.map((t) => t.key);
    expect(keys).not.toContain("composite");
    expect(keys).not.toContain("overall");
  });

  it("builds a horizontal bar trace in ascending-for-plot order (highest value rendered at top)", () => {
    // Plotly draws the first y-category at the bottom; feeding ascending order
    // puts the highest bar at the top of the chart.
    const traces = buildCentralityBarTraces(hubs, "degree", "#6b7f5e") as {
      x: number[];
      y: string[];
      orientation: string;
    }[];
    const trace = traces[0]!;
    expect(trace.orientation).toBe("h");
    // AKT1 has degree 12 (highest) → last in ascending list → rendered at top
    expect(trace.y).toEqual(["TP53", "AKT1"]); // ascending-for-plot: lowest at bottom, highest at top
    expect(trace.x).toEqual([9, 12]);
  });

  it("sorts correctly for MCC metric", () => {
    const traces = buildCentralityBarTraces(hubs, "mcc", "#6b7f5e") as {
      x: number[];
      y: string[];
    }[];
    const trace = traces[0]!;
    // TP53=120 highest; AKT1=80 lowest → ascending-for-plot: AKT1 first, TP53 last
    expect(trace.y).toEqual(["AKT1", "TP53"]);
    expect(trace.x).toEqual([80, 120]);
  });
});
