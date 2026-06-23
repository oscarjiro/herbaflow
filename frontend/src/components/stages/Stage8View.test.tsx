import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/lib/theme";
import { Stage8View } from "./Stage8View";
import type { AnalysisRead } from "../../api/types.gen";

// ---------------------------------------------------------------------------
// Mock EnrichmentDotChart (uses Plotly/lazy) to avoid dynamic-import failures
// in jsdom. The Stage8View gating and table behavior are still covered.
// ---------------------------------------------------------------------------

vi.mock("@/components/charts/EnrichmentDotChart", () => ({
  EnrichmentDotChart: () => <div data-testid="enrichment-dot-chart" />,
}));

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>
  );
}

async function openEnrichmentPanel() {
  await userEvent.click(screen.getByRole("button", { name: /enrichment parameters/i }));
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
    const { container } = render(wrap(<Stage8View data={data} />));
    const stage8 = container.firstElementChild as HTMLElement;
    expect(screen.getAllByText("PI3K-Akt").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText(/Background: compound target universe \(800 genes\)\./i),
    ).toHaveTextContent("Custom universe, not the whole genome.");
    expect(stage8).not.toHaveTextContent("—");
    expect(stage8).not.toHaveTextContent("methodologically-correct");
    expect(stage8).not.toHaveTextContent("honest null");
    expect(stage8).not.toHaveTextContent("Pipeline complete");
    // Interactive chart replaces the six server-rendered PNGs.
    expect(screen.getByText("Pathway enrichment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
    expect(document.querySelector('img[src*="stage8_enrichment_"]')).not.toBeInTheDocument();
  });

  it("renders the enrichment param panel with no_iea control", async () => {
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
    await openEnrichmentPanel();
    expect(screen.getByLabelText("Significance threshold (corrected p ≤)")).toBeInTheDocument();
    expect(screen.getByLabelText("Exclude electronic annotations (IEA)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument();
  });

  it("surfaces Reactome and WikiPathways enrichment source options", async () => {
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
    await openEnrichmentPanel();
    expect(screen.getByLabelText("Reactome")).toBeInTheDocument();
    expect(screen.getByLabelText("WikiPathways")).toBeInTheDocument();
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
      screen.getByText(
        "g:Profiler was unavailable. Enrichment was skipped, but the run still completed.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the enrichment chart once terms exist, even before the run completes", () => {
    const data = {
      ...base,
      status: "stage_8_awaiting_approval",
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

    expect(screen.getByText("Pathway enrichment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
  });

  it("does not render the enrichment chart when there are no terms", () => {
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
          degraded: false,
          count: 0,
          flags: [],
        },
      },
    } as unknown as AnalysisRead;

    render(wrap(<Stage8View data={data} />));

    expect(screen.queryByText("Pathway enrichment")).toBeNull();
    expect(screen.queryByRole("button", { name: /download png/i })).toBeNull();
  });
});
