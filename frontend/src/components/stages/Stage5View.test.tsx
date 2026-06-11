import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { Stage5View } from "./Stage5View";
import type { AnalysisRead } from "../../api/types.gen";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeStage5Result(overrides?: {
  significant?: boolean;
  flags?: string[];
  overlap?: object[];
}) {
  return {
    overlap: overrides?.overlap ?? [
      {
        target_id: "T1",
        gene_symbol: "EGFR",
        uniprot_accession: "P00533",
        disease_association_score: 0.85,
      },
      {
        target_id: "T2",
        gene_symbol: "TP53",
        uniprot_accession: "P04637",
        disease_association_score: 0.72,
      },
    ],
    count: 2,
    compound_target_count: 40,
    disease_target_count: 30,
    union_count: 68,
    jaccard: 0.029,
    hypergeometric: {
      background_n: 20000,
      K: 30,
      n: 40,
      k: 2,
      p_value: 0.0012,
      alpha: 0.05,
      significant: overrides?.significant ?? true,
    },
    unmapped_count: 0,
    state: "computed",
    flags: overrides?.flags ?? [],
  };
}

function makeData(overrides?: { significant?: boolean; flags?: string[] }): AnalysisRead {
  return {
    analysis_id: "a1",
    status: "stage_5_awaiting_approval",
    current_stage: 5,
    parameters: {},
    stage_results: {
      "5": makeStage5Result(overrides),
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

describe("Stage5View — significant overlap", () => {
  it("renders the overlap count card", () => {
    wrap(<Stage5View data={makeData({ significant: true })} />);
    expect(screen.getByLabelText(/2 overlap targets/i)).toBeInTheDocument();
  });

  it("renders the significant badge", () => {
    wrap(<Stage5View data={makeData({ significant: true })} />);
    expect(screen.getByText("significant")).toBeInTheDocument();
  });

  it("renders both gene-symbol rows", () => {
    wrap(<Stage5View data={makeData({ significant: true })} />);
    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.getByText("TP53")).toBeInTheDocument();
  });

  it("renders the CSV download control", () => {
    wrap(<Stage5View data={makeData({ significant: true })} />);
    expect(screen.getByRole("link", { name: /download csv/i })).toBeInTheDocument();
  });

  it("does not render a param panel or Redo button", () => {
    wrap(<Stage5View data={makeData({ significant: true })} />);
    expect(screen.queryByRole("button", { name: /redo/i })).toBeNull();
    expect(screen.queryByText(/parameters/i)).toBeNull();
  });
});

describe("Stage5View — non-significant overlap", () => {
  it("renders the not-significant badge when significant=false and flag set", () => {
    wrap(
      <Stage5View data={makeData({ significant: false, flags: ["non_significant_overlap"] })} />,
    );
    expect(screen.getByText("not significant")).toBeInTheDocument();
    expect(screen.queryByText("significant")).toBeNull();
  });
});
