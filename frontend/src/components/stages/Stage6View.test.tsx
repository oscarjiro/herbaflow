import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@/lib/theme";

// Mock react-cytoscapejs so the graph never really renders in jsdom.
vi.mock("react-cytoscapejs", () => ({
  default: ({ cy, elements }: { cy?: (c: unknown) => void; elements?: unknown[] }) => {
    cy?.({ png: () => "data:image/png;base64,AAAA" });
    return React.createElement("div", {
      "data-testid": "cytoscape",
      "data-count": String(elements?.length ?? 0),
    });
  },
}));

import { Stage6View } from "./Stage6View";
import type { AnalysisRead } from "../../api/types.gen";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeComputedResult() {
  return {
    state: "computed",
    nodes: [
      { gene_symbol: "EGFR", string_id: "9606.ENSP00000275493" },
      { gene_symbol: "TP53", string_id: "9606.ENSP00000269305" },
    ],
    edges: [{ source: "EGFR", target: "TP53", confidence: 0.92 }],
    node_count: 2,
    edge_count: 1,
    min_confidence: 0.4,
    network_type: "functional",
    unmapped: [],
    capped: { applied: false, max_proteins: 2000, ranked_by: "opentargets_score" },
    count: 2,
    flags: [],
  };
}

function makeBlockedResult() {
  return {
    blocked: true,
    reason: "overlap_too_large",
    overlap_count: 60,
    max_proteins: 50,
  };
}

const PPI_PARAM_VALUES = {
  min_confidence: 0.4,
  max_proteins: 2000,
  allow_top_n_cap: false,
  network_type: "functional",
};

function makeData(result: object, overrides: Partial<AnalysisRead> = {}): AnalysisRead {
  return {
    analysis_id: "a1",
    status: "stage_6_awaiting_approval",
    current_stage: 6,
    parameters: { ppi: PPI_PARAM_VALUES },
    stage_results: {
      "6": result,
    },
    stage_state: {},
    plants: [],
    diseases: [],
    compounds: [],
    ...overrides,
  } as unknown as AnalysisRead;
}

// A complete run whose Stage-6 network has a connected pair (EGFR-TP53) plus an
// isolated node (ABCA1) that participates in no kept edge, and a Stage-7 hub map.
function makeCompleteNetworkData(): AnalysisRead {
  return makeData(
    {
      ...makeComputedResult(),
      nodes: [
        { gene_symbol: "EGFR", string_id: "9606.ENSP00000275493" },
        { gene_symbol: "TP53", string_id: "9606.ENSP00000269305" },
        { gene_symbol: "ABCA1", string_id: "9606.ENSP00000374736" },
      ],
      node_count: 3,
    },
    {
      status: "complete",
      stage_results: {
        "6": {
          ...makeComputedResult(),
          nodes: [
            { gene_symbol: "EGFR", string_id: "9606.ENSP00000275493" },
            { gene_symbol: "TP53", string_id: "9606.ENSP00000269305" },
            { gene_symbol: "ABCA1", string_id: "9606.ENSP00000374736" },
          ],
          node_count: 3,
        },
        "7": { hubs: [{ rank: 1, target_id: "t1", gene_symbol: "EGFR", mcc: 12 }] },
      },
    } as unknown as Partial<AnalysisRead>,
  );
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>,
  );
}

async function openPpiPanel() {
  await userEvent.click(screen.getByRole("button", { name: /ppi network parameters/i }));
}

// ---------------------------------------------------------------------------
// Tests — computed network
// ---------------------------------------------------------------------------

describe("Stage6View — computed network", () => {
  it("renders the cleaned Step 6 heading", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    expect(screen.getByText("Step 6: PPI Network")).toBeInTheDocument();
  });

  it("renders the node and edge summary cards", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    expect(screen.getByLabelText(/2 nodes/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/1 edges/i)).toBeInTheDocument();
  });

  it("renders the edge row", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.getByText("TP53")).toBeInTheDocument();
    expect(screen.getByText("0.92")).toBeInTheDocument();
  });

  it("renders the CSV download control", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    expect(screen.getByRole("link", { name: /download csv/i })).toBeInTheDocument();
  });

  it("renders the ppi param panel including the network_type select and a Redo button", async () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    await openPpiPanel();
    // numeric + boolean + both enum selects are present
    expect(screen.getByLabelText("max_proteins")).toBeInTheDocument();
    expect(screen.getByLabelText("allow_top_n_cap")).toBeInTheDocument();
    expect(screen.getByLabelText("Minimum confidence")).toBeInTheDocument();
    expect(screen.getByLabelText("Network type")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument();
  });

  it("does not render the overlap-too-large prompt when computed", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    expect(screen.queryByText(/overlap too large/i)).toBeNull();
  });

  it("renders the cleaned no-node approval reason", () => {
    wrap(
      <Stage6View
        data={makeData({
          ...makeComputedResult(),
          nodes: [],
          edges: [],
          node_count: 0,
          edge_count: 0,
          count: 0,
        })}
      />,
    );
    expect(
      screen.getByText("No PPI nodes. Adjust the parameters and Redo, or narrow the inputs."),
    ).toBeInTheDocument();
  });

  it("uses cleaned stale approval copy", () => {
    const data = makeData({ ...makeComputedResult(), stale: true });
    data.parameters = { ppi: PPI_PARAM_VALUES, rerun_from: 5 } as AnalysisRead["parameters"];

    wrap(<Stage6View data={data} />);

    expect(screen.getByRole("button", { name: /approve & continue/i })).toBeDisabled();
    expect(screen.getByText("Run the updated step before continuing.")).toBeInTheDocument();
    expect(
      screen.queryByText("Re-run the out-of-date step before continuing."),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — interactive network graph (complete run)
// ---------------------------------------------------------------------------

describe("Stage6View — interactive network graph", () => {
  it("renders the interaction network frame with a Download PNG control", () => {
    wrap(<Stage6View data={makeCompleteNetworkData()} />);
    expect(screen.getByText("Interaction network")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
  });

  it("does not render the old server-rendered PPI image", () => {
    wrap(<Stage6View data={makeCompleteNetworkData()} />);
    const imgs = screen.queryAllByRole("img");
    expect(imgs.some((el) => el.getAttribute("src")?.includes("stage6_ppi_network.png"))).toBe(
      false,
    );
  });

  it("lists an edge-less node in the not-connected tray", () => {
    wrap(<Stage6View data={makeCompleteNetworkData()} />);
    expect(screen.getByText(/not connected at this confidence/i)).toHaveTextContent("ABCA1");
  });

  it("does not render the graph when the run is not complete", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    expect(screen.queryByText("Interaction network")).toBeNull();
  });

  it("still renders the edge-list table alongside the graph", () => {
    wrap(<Stage6View data={makeCompleteNetworkData()} />);
    expect(screen.getByRole("link", { name: /download csv/i })).toBeInTheDocument();
    expect(screen.getByText("0.92")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — blocked (overlap too large)
// ---------------------------------------------------------------------------

describe("Stage6View — overlap too large (blocked)", () => {
  it("renders the overlap-too-large prompt with the counts", () => {
    wrap(<Stage6View data={makeData(makeBlockedResult())} />);
    // the badge text (the ApprovalBar reason also contains the phrase, so match exactly)
    expect(screen.getByText("Overlap too large")).toBeInTheDocument();
    // the prompt mentions the overlap count and the ceiling
    expect(screen.getByText(/60 proteins/i)).toBeInTheDocument();
  });

  it("renders the Enable top-N & Redo affordance", () => {
    wrap(<Stage6View data={makeData(makeBlockedResult())} />);
    expect(screen.getByRole("button", { name: /enable top-n cap and redo/i })).toBeInTheDocument();
  });

  it("renders the cleaned blocked approval reason", () => {
    wrap(<Stage6View data={makeData(makeBlockedResult())} />);
    expect(
      screen.getByText("Overlap too large. Enable the top-N cap and Redo, or narrow the inputs."),
    ).toBeInTheDocument();
  });

  it("does NOT render the edge table when blocked", () => {
    wrap(<Stage6View data={makeData(makeBlockedResult())} />);
    // no edge-table headers
    expect(screen.queryByText("Source")).toBeNull();
    expect(screen.queryByText("Target")).toBeNull();
    expect(screen.queryByRole("link", { name: /download csv/i })).toBeNull();
  });

  it("still renders the ppi param panel when blocked", async () => {
    wrap(<Stage6View data={makeData(makeBlockedResult())} />);
    await openPpiPanel();
    expect(screen.getByLabelText("max_proteins")).toBeInTheDocument();
    expect(screen.getByLabelText("Network type")).toBeInTheDocument();
  });
});
