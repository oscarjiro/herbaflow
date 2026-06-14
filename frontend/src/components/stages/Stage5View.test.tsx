import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { Stage5View } from "./Stage5View";
import type { AnalysisRead } from "../../api/types.gen";

function makeStage5Result(overrides?: { overlap?: object[] }) {
  return {
    overlap: overrides?.overlap ?? [
      {
        target_id: "T1",
        gene_symbol: "EGFR",
        uniprot_accession: "P00533",
        opentargets_score: 0.85,
      },
      {
        target_id: "T2",
        gene_symbol: "TP53",
        uniprot_accession: "P04637",
        opentargets_score: 0.72,
      },
    ],
    count: 2,
    compound_target_count: 40,
    disease_target_count: 30,
    unmapped_count: 0,
    state: "computed",
    flags: [],
  };
}

function makeData(overrides?: { overlap?: object[] }): AnalysisRead {
  return {
    analysis_id: "a1",
    status: "stage_5_awaiting_approval",
    current_stage: 5,
    parameters: {},
    stage_results: { "5": makeStage5Result(overrides) },
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

describe("Stage5View — overlap view", () => {
  it("renders the overlap count card", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.getByLabelText(/2 overlap targets/i)).toBeInTheDocument();
  });

  it("renders both gene-symbol rows", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.getByText("TP53")).toBeInTheDocument();
  });

  it("renders the CSV download control", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.getByRole("link", { name: /download csv/i })).toBeInTheDocument();
  });

  it("does NOT render Jaccard, p-value, or a significance badge", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.queryByText(/jaccard/i)).toBeNull();
    expect(screen.queryByText(/p-value/i)).toBeNull();
    expect(screen.queryByText(/significant/i)).toBeNull();
  });

  it("does not render a param panel or Redo button", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.queryByRole("button", { name: /redo/i })).toBeNull();
    expect(screen.queryByText(/parameters/i)).toBeNull();
  });

  it("shows the venn image when complete", () => {
    const completeData: AnalysisRead = {
      ...makeData(),
      status: "complete",
    } as unknown as AnalysisRead;
    wrap(<Stage5View data={completeData} />);
    expect(screen.getByRole("img", { name: /overlap/i })).toHaveAttribute(
      "src",
      expect.stringContaining("/export/stage5_venn.png"),
    );
  });

  it("does not show the venn image when not complete", () => {
    wrap(<Stage5View data={makeData()} />);
    expect(screen.queryByRole("img", { name: /overlap/i })).toBeNull();
  });
});
