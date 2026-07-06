import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/lib/theme";
import { Stage8View, buildS8CsvRows, S8_CSV_HEADER } from "./Stage8View";
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
    expect(screen.getByText("Functional enrichment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
    expect(document.querySelector('img[src*="stage8_enrichment_"]')).not.toBeInTheDocument();
    // E1: the correction method is humanized on the summary card as a compact form
    // (not the raw "fdr" enum), with the full name available via the title tooltip.
    expect(screen.getByText("BH-FDR")).toBeInTheDocument();
    expect(screen.getByTitle("Benjamini-Hochberg FDR")).toBeInTheDocument();
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

    expect(screen.getByText("Functional enrichment")).toBeInTheDocument();
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

    expect(screen.queryByText("Functional enrichment")).toBeNull();
    expect(screen.queryByRole("button", { name: /download png/i })).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // New: term-page link, genes-in-term cell, CSV columns — realistic enum fixture
  // ---------------------------------------------------------------------------

  const REALISTIC_TERMS = [
    {
      source: "GO:BP",
      term_id: "GO:0006915",
      name: "apoptotic process",
      p_value: 1.2e-8,
      term_size: 1200,
      query_size: 10,
      intersection_size: 5,
      intersection: ["CASP3", "TP53", "BCL2", "BAX", "CYCS"],
    },
    {
      source: "KEGG",
      term_id: "KEGG:04151",
      name: "PI3K-Akt signaling pathway",
      p_value: 3.1e-6,
      term_size: 354,
      query_size: 10,
      intersection_size: 4,
      intersection: ["AKT1", "AKT2", "PIK3CA", "MTOR"],
    },
    {
      source: "REAC",
      term_id: "REAC:R-HSA-109581",
      name: "Apoptosis",
      p_value: 2.4e-7,
      term_size: 180,
      query_size: 10,
      intersection_size: 3,
      intersection: ["CASP3", "TP53", "BCL2"],
    },
    {
      source: "WP",
      term_id: "WP:WP254",
      name: "Apoptosis",
      p_value: 5.0e-5,
      term_size: 90,
      query_size: 10,
      intersection_size: 2,
      intersection: ["CASP3", "TP53"],
    },
  ] as const;

  type EnrichmentTermFixture = {
    source: string;
    term_id: string;
    name: string;
    p_value: number;
    term_size: number;
    query_size: number;
    intersection_size: number;
    intersection: readonly string[];
  };

  function makeRealisticData(terms: readonly EnrichmentTermFixture[]): AnalysisRead {
    return {
      ...base,
      status: "complete",
      stage_results: {
        "8": {
          state: "computed",
          terms,
          input_gene_count: 10,
          background_gene_count: 1200,
          background_source: "compound_target_universe",
          correction: "fdr",
          significance_threshold: 0.05,
          min_term_size: 5,
          sources: ["GO:BP", "KEGG", "REAC", "WP"],
          degraded: false,
          count: terms.length,
          flags: [],
        },
      },
    } as unknown as AnalysisRead;
  }

  it("term name is a link to the correct term page (GO, KEGG, REAC, WP)", () => {
    render(wrap(<Stage8View data={makeRealisticData(REALISTIC_TERMS)} />));

    // GO:BP → QuickGO
    const goLink = screen.getByRole("link", { name: /apoptotic process/i });
    expect(goLink).toHaveAttribute("href", "https://www.ebi.ac.uk/QuickGO/term/GO:0006915");

    // KEGG → kegg.jp (bare id after stripping "KEGG:" prefix)
    const keggLink = screen.getByRole("link", { name: /PI3K-Akt signaling pathway/i });
    expect(keggLink).toHaveAttribute("href", "https://www.kegg.jp/entry/04151");

    // REAC → Reactome and WP → WikiPathways (both named "Apoptosis")
    const allApoptosisLinks = screen.getAllByRole("link", { name: /Apoptosis/i });
    const reacApoptosis = allApoptosisLinks.find((el) =>
      el.getAttribute("href")?.includes("reactome.org"),
    );
    const wpApoptosis = allApoptosisLinks.find((el) =>
      el.getAttribute("href")?.includes("wikipathways.org"),
    );
    expect(reacApoptosis).toHaveAttribute(
      "href",
      "https://reactome.org/content/detail/R-HSA-109581",
    );
    expect(wpApoptosis).toHaveAttribute("href", "https://www.wikipathways.org/pathways/WP254");
  });

  it("downloads enrichment terms with the bare CSV slug", () => {
    render(wrap(<Stage8View data={makeRealisticData(REALISTIC_TERMS)} />));
    const link = screen.getByRole("link", { name: /download csv/i });
    expect(link).toHaveAttribute("download", "enrichment.csv");
  });

  it("labels the enrichment source column as Category", () => {
    render(wrap(<Stage8View data={makeRealisticData(REALISTIC_TERMS)} />));

    // The Category header now carries an info tooltip, so its accessible name includes the
    // circle-i affordance; match the label rather than the exact string.
    expect(screen.getByRole("columnheader", { name: /Category/i })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
  });

  it("renders the enrichment chart before the terms table", () => {
    render(wrap(<Stage8View data={makeRealisticData(REALISTIC_TERMS)} />));
    const chartTitle = screen.getByText("Functional enrichment");
    const csvLink = screen.getByRole("link", { name: /download csv/i });

    expect(
      chartTitle.compareDocumentPosition(csvLink) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("passes every enrichment row to DataTable so the shared pager owns pagination", () => {
    const terms = Array.from({ length: 12 }, (_, i) => ({
      source: "GO:BP",
      term_id: `GO:${String(i).padStart(7, "0")}`,
      name: `term ${i}`,
      p_value: 0.001 + i / 10000,
      term_size: 100 + i,
      query_size: 10,
      intersection_size: 2,
      intersection: ["AKT1", "TNF"],
    }));

    render(wrap(<Stage8View data={makeRealisticData(terms)} />));

    expect(screen.getByText("Showing 1–10 of 12")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Previous" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("genes-in-term cell shows a collapsed count and expands to gene chips", async () => {
    render(wrap(<Stage8View data={makeRealisticData([REALISTIC_TERMS[0]])} />));

    // With collapsedCount=0, all genes are hidden behind "+5 more" in collapsed state.
    const expandBtn = screen.getByRole("button", { name: /\+5 more/i });
    expect(expandBtn).toBeInTheDocument();

    // Expand: gene chips become visible
    await userEvent.click(expandBtn);
    expect(screen.getByText("CASP3")).toBeInTheDocument();
    expect(screen.getByText("TP53")).toBeInTheDocument();
    expect(screen.getByText("BCL2")).toBeInTheDocument();
    expect(screen.getByText("BAX")).toBeInTheDocument();
    expect(screen.getByText("CYCS")).toBeInTheDocument();

    // Collapse again via "Show less"
    await userEvent.click(screen.getByRole("button", { name: /show less/i }));
    expect(screen.queryByText("CYCS")).not.toBeInTheDocument();
  });

  it("CSV header includes term_url and term_genes; row serialises gene list semicolon-joined", () => {
    expect(S8_CSV_HEADER).toContain("term_url");
    expect(S8_CSV_HEADER).toContain("term_genes");

    const rows = buildS8CsvRows([
      {
        source: "GO:BP",
        term_id: "GO:0006915",
        name: "apoptotic process",
        p_value: 1.2e-8,
        term_size: 1200,
        query_size: 10,
        intersection_size: 5,
        intersection: ["CASP3", "TP53", "BCL2", "BAX", "CYCS"],
      },
      {
        source: "KEGG",
        term_id: "KEGG:04151",
        name: "PI3K-Akt signaling pathway",
        p_value: 3.1e-6,
        term_size: 354,
        query_size: 10,
        intersection_size: 4,
        intersection: ["AKT1", "AKT2", "PIK3CA", "MTOR"],
      },
    ]);

    // GO:BP row
    const goRow = rows[0] as unknown[];
    const goUrl = goRow[7];
    const goGenes = goRow[8];
    expect(goUrl).toBe("https://www.ebi.ac.uk/QuickGO/term/GO:0006915");
    expect(goGenes).toBe("CASP3;TP53;BCL2;BAX;CYCS");

    // KEGG row
    const keggRow = rows[1] as unknown[];
    const keggUrl = keggRow[7];
    const keggGenes = keggRow[8];
    expect(keggUrl).toBe("https://www.kegg.jp/entry/04151");
    expect(keggGenes).toBe("AKT1;AKT2;PIK3CA;MTOR");

    // Existing columns still present (source, term_id, name, p_value, term_size, intersection_size, intersection)
    expect(goRow[0]).toBe("GO:BP");
    expect(goRow[1]).toBe("GO:0006915");
    expect(goRow[3]).toBe(1.2e-8);
  });
});
