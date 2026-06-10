import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Stage3View } from "../src/components/stages/Stage3View";
import type { AnalysisRead } from "../src/api/types.gen";
import "../src/lib/api";

const TARGET_FROZEN = {
  min_pchembl: 5,
  min_assay_confidence: 0.5,
};

const TARGET_ID = "11111111-1111-1111-1111-111111111111";

// One covered compound (c1 → TP53/P04637 via ChEMBL) and one 0-coverage compound (c2).
const SAMPLE_STAGE3_RESULTS = {
  targets: [{ target_id: TARGET_ID, canonical_name: "TP53", tag: "computed" }],
  compound_targets: [
    {
      compound_id: "c1",
      target_id: TARGET_ID,
      prediction_method: "chembl_bioactivity",
      pchembl_value: 6.2,
      score: null,
      source_url: "https://www.uniprot.org/uniprotkb/P04637",
      uniprot_accession: "P04637",
    },
  ],
  per_compound: {
    c1: { coverage: 1 },
    c2: { coverage: 0 },
  },
  coverage_pct: 50,
  count: 1,
  state: "computed",
};

const SAMPLE_STAGE2_PASSED = {
  count: 2,
  state: "computed",
  passed: [
    { compound_id: "c1", canonical_name: "Curcumin", smiles: "CCO" },
    { compound_id: "c2", canonical_name: "Berberine", smiles: "CCN" },
  ],
  filtered: [],
  annotations: { pains: [], np_bypass: [], unscreened: [], could_not_screen: [] },
};

function makeRun(overrides: Partial<AnalysisRead> = {}): AnalysisRead {
  return {
    analysis_id: "r3t",
    analysis_name: null,
    disease_id: "d1",
    mode: "guided",
    status: "stage_3_awaiting_approval",
    current_stage: 3,
    parameters: { target: TARGET_FROZEN },
    stage_results: { "2": SAMPLE_STAGE2_PASSED, "3": SAMPLE_STAGE3_RESULTS },
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
    ...overrides,
  };
}

function wrap(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

/** Scope queries to the per-target table (inside .table-wrapper). */
function targetsTable(container: HTMLElement) {
  const el = container.querySelector(".table-wrapper");
  if (!el) throw new Error("targets table not found");
  return within(el as HTMLElement);
}

/** Read a captured Blob to text via FileReader (jsdom Blob.text() is unreliable). */
function blobToText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Stage3View", () => {
  it("renders the gene symbol in the targets table", () => {
    const { container } = wrap(<Stage3View data={makeRun()} />);
    expect(targetsTable(container).getByText("TP53")).toBeInTheDocument();
  });

  it("renders the UniProt accession as a link to its source_url", () => {
    wrap(<Stage3View data={makeRun()} />);
    const link = screen.getByRole("link", { name: "P04637" });
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P04637");
  });

  it("shows the evidence/method column", () => {
    const { container } = wrap(<Stage3View data={makeRun()} />);
    // The method cell in the targets table shows "ChEMBL".
    expect(targetsTable(container).getByText("ChEMBL")).toBeInTheDocument();
  });

  it("shows the coverage percentage card", () => {
    wrap(<Stage3View data={makeRun()} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("shows per-source ChEMBL edge count", () => {
    wrap(<Stage3View data={makeRun()} />);
    // ChEMBL source card label exists with value 1
    expect(screen.getByRole("generic", { name: /1 ChEMBL edges/i })).toBeInTheDocument();
  });

  it("keeps the 0-coverage compound row visible", () => {
    const { container } = wrap(<Stage3View data={makeRun()} />);
    const coverage = container.querySelector(".coverage-table") as HTMLElement;
    expect(coverage).not.toBeNull();
    // Berberine (c2) has coverage 0 and must still render in the coverage table.
    const cell = within(coverage).getByText("Berberine");
    expect(cell).toBeInTheDocument();
    expect(cell.closest("tr")).toHaveClass("row--zero-coverage");
  });

  it("CSV is keyed on gene symbol/uniprot/method/source_url and has NO UUID column", async () => {
    // Capture the Blob passed to URL.createObjectURL so we can inspect the CSV.
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      capturedBlob = blob as Blob;
      return "blob:mock";
    });

    wrap(<Stage3View data={makeRun()} />);
    // The download link must be present.
    expect(screen.getByRole("link", { name: /download.*csv/i })).toBeInTheDocument();

    expect(capturedBlob).not.toBeNull();
    const csv = await blobToText(capturedBlob as unknown as Blob);

    // Headers are the human-meaningful keys.
    expect(csv).toContain("gene_symbol");
    expect(csv).toContain("uniprot_accession");
    expect(csv).toContain("prediction_method");
    expect(csv).toContain("source_url");

    // Data row content present.
    expect(csv).toContain("TP53");
    expect(csv).toContain("P04637");

    // HARD REQUIREMENT: never a UUID column / value.
    expect(csv).not.toContain("target_id");
    expect(csv).not.toContain(TARGET_ID);
  });

  it("greys out the view when stage_state is not_applicable", () => {
    const data = makeRun();
    (data as { stage_state?: Record<string, string> }).stage_state = { "3": "not_applicable" };
    wrap(<Stage3View data={data} />);
    expect(screen.getByText(/not applicable/i)).toBeInTheDocument();
    // No targets table content.
    expect(screen.queryByText("TP53")).not.toBeInTheDocument();
  });

  it("user_provided renders targets only (no coverage table, no STP dialog)", () => {
    const data = makeRun();
    (data as { stage_state?: Record<string, string> }).stage_state = { "3": "user_provided" };
    const { container } = wrap(<Stage3View data={data} />);
    // Target still rendered in the table.
    expect(targetsTable(container).getByText("TP53")).toBeInTheDocument();
    // No per-compound coverage section and no STP dialog.
    expect(screen.queryByText(/per-compound coverage/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: /swisstargetprediction import/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps STP dialog + coverage when the edit layer marks the result user_provided", () => {
    // A computed run that has been edited: the durable edit layer sets the stored
    // stage-3 result.state to "user_provided", but there is NO entry-mode stage_state.
    // The view must stay the full computed view so the STP/coverage workflow survives edits.
    const data = makeRun({
      stage_results: {
        "2": SAMPLE_STAGE2_PASSED,
        "3": { ...SAMPLE_STAGE3_RESULTS, state: "user_provided" },
      },
    });
    wrap(<Stage3View data={data} />);
    expect(screen.getByText(/per-compound coverage/i)).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /swisstargetprediction import/i }),
    ).toBeInTheDocument();
  });
});
