import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stage8View } from "./Stage8View";
import type { AnalysisRead } from "../../api/types.gen";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

const base = {
  analysis_id: "11111111-1111-1111-1111-111111111111",
  current_stage: 8,
  parameters: {
    enrichment: {
      significance_threshold: 0.05,
      sources: ["GO:BP", "KEGG"],
      correction: "fdr",
      min_term_size: 5,
      no_iea: false,
    },
  },
} as const;

describe("Stage8View", () => {
  it("renders enriched terms", () => {
    const data = {
      ...base,
      status: "complete",
      stage_results: {
        "8": {
          state: "computed",
          terms: [
            {
              source: "KEGG",
              term_id: "KEGG:04151",
              name: "PI3K-Akt",
              p_value: 3.1e-6,
              term_size: 354,
              query_size: 3,
              intersection_size: 2,
              intersection: ["AKT1", "TNF"],
            },
          ],
          input_gene_count: 3,
          background_gene_count: 800,
          background_source: "compound_target_universe",
          correction: "fdr",
          significance_threshold: 0.05,
          min_term_size: 5,
          sources: ["GO:BP", "KEGG"],
          degraded: false,
          count: 1,
          flags: [],
        },
      },
    } as unknown as AnalysisRead;
    render(wrap(<Stage8View data={data} />));
    expect(screen.getByText("Step 8 — Functional Enrichment")).toBeInTheDocument();
    expect(screen.getByText("PI3K-Akt")).toBeInTheDocument();
  });

  it("renders the enrichment param panel with no_iea control", () => {
    const data = {
      ...base,
      status: "complete",
      stage_results: {
        "8": {
          state: "computed",
          terms: [],
          input_gene_count: 3,
          background_gene_count: 800,
          background_source: "compound_target_universe",
          correction: "fdr",
          significance_threshold: 0.05,
          min_term_size: 5,
          sources: ["GO:BP", "KEGG"],
          degraded: false,
          count: 0,
          flags: [],
        },
      },
    } as unknown as AnalysisRead;
    render(wrap(<Stage8View data={data} />));
    expect(screen.getByLabelText("significance_threshold")).toBeInTheDocument();
    expect(screen.getByLabelText("no_iea")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument();
  });

  it("shows the degraded notice", () => {
    const data = {
      ...base,
      status: "complete",
      stage_results: {
        "8": {
          state: "computed",
          terms: [],
          input_gene_count: 3,
          background_gene_count: 800,
          background_source: "compound_target_universe",
          correction: "fdr",
          significance_threshold: 0.05,
          min_term_size: 5,
          sources: ["GO:BP"],
          degraded: true,
          count: 0,
          flags: ["source_degraded"],
        },
      },
    } as unknown as AnalysisRead;
    render(wrap(<Stage8View data={data} />));
    expect(
      screen.getByText(/g:Profiler was unavailable — enrichment was skipped/i),
    ).toBeInTheDocument();
  });
});
