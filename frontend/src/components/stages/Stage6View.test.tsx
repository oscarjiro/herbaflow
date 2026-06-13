import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
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

function makeData(result: object): AnalysisRead {
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
  } as unknown as AnalysisRead;
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests — computed network
// ---------------------------------------------------------------------------

describe("Stage6View — computed network", () => {
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

  it("renders the ppi param panel including the network_type select and a Redo button", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    // numeric + boolean + both enum selects are present
    expect(screen.getByLabelText("max_proteins")).toBeInTheDocument();
    expect(screen.getByLabelText("allow_top_n_cap")).toBeInTheDocument();
    expect(screen.getByLabelText("min_confidence")).toBeInTheDocument();
    expect(screen.getByLabelText("network_type")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument();
  });

  it("does not render the overlap-too-large prompt when computed", () => {
    wrap(<Stage6View data={makeData(makeComputedResult())} />);
    expect(screen.queryByText(/overlap too large/i)).toBeNull();
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

  it("does NOT render the edge table when blocked", () => {
    wrap(<Stage6View data={makeData(makeBlockedResult())} />);
    // no edge-table headers
    expect(screen.queryByText("Source")).toBeNull();
    expect(screen.queryByText("Target")).toBeNull();
    expect(screen.queryByRole("link", { name: /download csv/i })).toBeNull();
  });

  it("still renders the ppi param panel when blocked", () => {
    wrap(<Stage6View data={makeData(makeBlockedResult())} />);
    expect(screen.getByLabelText("max_proteins")).toBeInTheDocument();
    expect(screen.getByLabelText("network_type")).toBeInTheDocument();
  });
});
