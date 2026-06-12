import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { Stage7View } from "./Stage7View";
import type { AnalysisRead } from "../../api/types.gen";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeComputedResult() {
  return {
    state: "computed",
    hubs: [
      {
        rank: 1,
        target_id: "t0",
        gene_symbol: "TNF",
        degree: 0.41,
        betweenness: 0.33,
        closeness: 0.58,
        eigenvector: 0.29,
        composite: 0.37,
        source_url: "https://www.uniprot.org/uniprotkb/P01375/entry",
      },
    ],
    ranking_metric: "hub_bottleneck_composite",
    composite_weight: 0.5,
    normalization: "min_max",
    node_count: 1,
    top_n: 20,
    count: 1,
    flags: [],
  };
}

const HUB_PARAM_VALUES = {
  top_n: 20,
  use_hub_bottleneck: true,
  composite_weight: 0.5,
};

function makeData(result: object): AnalysisRead {
  return {
    analysis_id: "11111111-1111-1111-1111-111111111111",
    status: "stage_7_awaiting_approval",
    current_stage: 7,
    parameters: { hub_genes: HUB_PARAM_VALUES },
    stage_results: {
      "7": result,
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
// Tests
// ---------------------------------------------------------------------------

describe("Stage7View", () => {
  it("renders the hub table with the gene and composite", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByText("Step 7 — Hub Genes")).toBeInTheDocument();
    expect(screen.getByText("TNF")).toBeInTheDocument();
    expect(screen.getByText("0.37")).toBeInTheDocument();
  });

  it("renders summary cards for node count and hub count", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByLabelText(/1 nodes/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/1 hubs/i)).toBeInTheDocument();
  });

  it("renders the CSV download control", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByRole("link", { name: /download csv/i })).toBeInTheDocument();
  });

  it("renders the hub_genes param panel with a Redo button", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByLabelText("top_n")).toBeInTheDocument();
    expect(screen.getByLabelText("use_hub_bottleneck")).toBeInTheDocument();
    expect(screen.getByLabelText("composite_weight")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument();
  });

  it("renders all four individual centrality columns", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByText("Degree")).toBeInTheDocument();
    expect(screen.getByText("Betweenness")).toBeInTheDocument();
    expect(screen.getByText("Closeness")).toBeInTheDocument();
    expect(screen.getByText("Eigenvector")).toBeInTheDocument();
  });
});
