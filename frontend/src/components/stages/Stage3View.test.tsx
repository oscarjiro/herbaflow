import type { ReactElement } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Stage3View } from "./Stage3View";
import * as sdk from "../../api/sdk.gen";
import * as toastLib from "../../lib/toast";
import type { AnalysisRead } from "../../api/types.gen";
import "../../lib/api";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const TARGET_FROZEN = {
  min_pchembl: 5,
  min_assay_confidence: 0.5,
};

const TARGET_ID = "11111111-1111-1111-1111-111111111111";

// One covered compound (c1 → TP53/P04637 via ChEMBL) and one 0-coverage compound (c2).
const SAMPLE_STAGE3_RESULTS = {
  targets: [
    {
      target_id: TARGET_ID,
      canonical_name: "TP53",
      gene_symbol: "TP53",
      uniprot_accession: "P04637",
      source_url: "https://www.uniprot.org/uniprotkb/P04637/entry",
      tag: "computed",
    },
  ],
  compound_targets: [
    {
      compound_id: "c1",
      target_id: TARGET_ID,
      prediction_method: "chembl_bioactivity",
      pchembl_value: 6.2,
      score: null,
      source_url: "https://www.uniprot.org/uniprotkb/P04637/entry",
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
    stage_state: {},
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
    ...overrides,
  } as unknown as AnalysisRead;
}

/** Minimal AnalysisRead whose stage-3 result already contains T1/AAA. */
function makeData(): AnalysisRead {
  return {
    analysis_id: "a1",
    status: "awaiting_approval",
    current_stage: 3,
    parameters: {},
    stage_results: {
      "3": {
        targets: [{ target_id: "T1", canonical_name: "AAA", tag: "computed" }],
        compound_targets: [],
        per_compound: {},
        coverage_pct: 100,
        count: 1,
        state: "computed",
      },
      "2": { passed: [] },
    },
    stage_state: { "3": "computed" },
    plants: [],
    diseases: [],
    compounds: [],
  } as unknown as AnalysisRead;
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

// ---------------------------------------------------------------------------
// Rendering / summary / CSV / gating
// ---------------------------------------------------------------------------

describe("Stage3View", () => {
  it("renders the gene symbol in the targets table", () => {
    const { container } = wrap(<Stage3View data={makeRun()} />);
    expect(targetsTable(container).getByText("TP53")).toBeInTheDocument();
  });

  it("renders the UniProt accession as a link to its UniProt entry page", () => {
    wrap(<Stage3View data={makeRun()} />);
    const link = screen.getByRole("link", { name: "P04637" });
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P04637/entry");
  });

  it("does not render a separate source column in the targets table", () => {
    const { container } = wrap(<Stage3View data={makeRun()} />);
    const table = targetsTable(container);
    expect(table.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    expect(table.queryByText("ChEMBL")).not.toBeInTheDocument();
  });

  it("shows the coverage percentage card", () => {
    wrap(<Stage3View data={makeRun()} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("shows per-source ChEMBL edge count", () => {
    wrap(<Stage3View data={makeRun()} />);
    // ChEMBL source card carries an aria-label with value 1.
    expect(screen.getByLabelText(/1 ChEMBL target links/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/1 ChEMBL edges/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/0 PubChem BioAssay target links/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/0 PubChem BioAssay edges/i)).not.toBeInTheDocument();
  });

  it("does NOT render the StaleNotice itself (the StageView shell owns it)", () => {
    // Even when Stage 3 is the edited stage (rerun_from === 3), the per-stage view no
    // longer renders its own StaleNotice — the shell is the sole home for the notice.
    wrap(
      <Stage3View
        data={makeRun({
          parameters: { target: TARGET_FROZEN, rerun_from: 3 },
          stage_results: {
            "2": SAMPLE_STAGE2_PASSED,
            "3": { ...SAMPLE_STAGE3_RESULTS, stale: true },
          } as unknown as AnalysisRead["stage_results"],
        })}
      />,
    );
    expect(
      screen.queryByText("These results are out of date. An earlier step changed."),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /re-run from step/i })).not.toBeInTheDocument();
  });

  it("keeps the 0-coverage compound row visible", () => {
    const { container } = wrap(<Stage3View data={makeRun()} />);
    const coverage = container.querySelector(".coverage-table") as HTMLElement;
    expect(coverage).not.toBeNull();
    // Berberine (c2) has coverage 0 and must still render in the coverage table.
    expect(within(coverage).getByText("Berberine")).toBeInTheDocument();
    // Curcumin (c1) covered, Berberine (c2) uncovered — both rendered.
    expect(within(coverage).getByText("Curcumin")).toBeInTheDocument();
  });

  it("CSV is keyed on gene symbol/uniprot/method/source_url and has NO UUID column", async () => {
    // Capture the Blob passed to URL.createObjectURL so we can inspect the CSV.
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      capturedBlob = blob as Blob;
      return "blob:mock";
    });

    wrap(<Stage3View data={makeRun()} />);
    // The download control must be present.
    expect(screen.getByRole("link", { name: /download.*csv/i })).toBeInTheDocument();

    expect(capturedBlob).not.toBeNull();
    const csv = await blobToText(capturedBlob as unknown as Blob);

    // Headers are the human-meaningful keys.
    expect(csv).toContain("gene_symbol");
    expect(csv).toContain("uniprot_accession");
    expect(csv).toContain("prediction_method");
    expect(csv).toContain("source_compounds");
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
    expect(
      screen.getByRole("heading", { name: "Step 3: Target Identification" }),
    ).toBeInTheDocument();
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
      screen.queryByRole("region", { name: /add targets from swisstargetprediction/i }),
    ).not.toBeInTheDocument();
  });

  it("does not render a stale STP edges summary card", () => {
    wrap(<Stage3View data={makeRun()} />);
    expect(screen.queryByText(/^STP$/)).not.toBeInTheDocument();
  });

  it("keeps STP dialog + coverage when the edit layer marks the result user_provided", () => {
    // A computed run that has been edited: the durable edit layer sets the stored
    // stage-3 result.state to "user_provided", but there is NO entry-mode stage_state.
    // The view must stay the full computed view so the STP/coverage workflow survives edits.
    const data = makeRun({
      stage_results: {
        "2": SAMPLE_STAGE2_PASSED,
        "3": { ...SAMPLE_STAGE3_RESULTS, state: "user_provided" },
      } as unknown as AnalysisRead["stage_results"],
    });
    wrap(<Stage3View data={data} />);
    expect(screen.getByText(/per-compound coverage/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add swisstargetprediction targets/i }),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Removed-row hiding + delete column
// ---------------------------------------------------------------------------

describe("Stage3View — removed-row hiding + delete column", () => {
  /** Stage-3 data with one computed row and one user-removed row. */
  function makeDataWithRemoved(): AnalysisRead {
    return {
      analysis_id: "a1",
      status: "awaiting_approval",
      current_stage: 3,
      parameters: {},
      stage_results: {
        "3": {
          targets: [
            { target_id: "t1", canonical_name: "PPARG", gene_symbol: "PPARG", tag: "computed" },
            { target_id: "t2", canonical_name: "TP53", gene_symbol: "TP53", tag: "user-removed" },
          ],
          compound_targets: [],
          per_compound: {},
          coverage_pct: 0,
          count: 1,
          state: "computed",
        },
        "2": { passed: [] },
      },
      stage_state: { "3": "computed" },
      plants: [],
      diseases: [],
      compounds: [],
    } as unknown as AnalysisRead;
  }

  it("hides user-removed rows and shows a delete column", () => {
    wrap(<Stage3View data={makeDataWithRemoved()} />);
    expect(screen.getByText("PPARG")).toBeInTheDocument();
    expect(screen.queryByText("TP53")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove PPARG" })).toHaveAttribute(
      "title",
      "Keep at least one target before removing another.",
    );
  });
});

// ---------------------------------------------------------------------------
// UniProt accession from the target row (B2)
// ---------------------------------------------------------------------------

describe("Stage3View — UniProt accession from the target row (B2)", () => {
  /** manual_targets: the row carries gene_symbol/uniprot_accession/source_url; no edges exist. */
  function makeUserProvidedData(): AnalysisRead {
    return {
      analysis_id: "a1",
      status: "failed",
      current_stage: 5,
      parameters: {},
      stage_results: {
        "3": {
          targets: [
            {
              target_id: "t1",
              canonical_name: "AKT1",
              gene_symbol: "AKT1",
              uniprot_accession: "P31749",
              source_url: "https://www.uniprot.org/uniprotkb/P31749/entry",
              tag: "user-added",
            },
          ],
          compound_targets: [],
          per_compound: {},
          coverage_pct: 0,
          count: 1,
          state: "user_provided",
        },
        "2": { passed: [] },
      },
      stage_state: { "3": "user_provided" },
      plants: [],
      diseases: [],
      compounds: [],
    } as unknown as AnalysisRead;
  }

  it("renders the linked accession from the row when there are no compound edges", () => {
    const { container } = wrap(<Stage3View data={makeUserProvidedData()} />);
    const link = screen.getByRole("link", { name: "P31749" });
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P31749/entry");
    const table = targetsTable(container);
    expect(table.queryByText("user-added")).not.toBeInTheDocument();
    expect(table.queryByText("User-curated")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Already-in-run deduplication
// ---------------------------------------------------------------------------

describe("Stage3View — already-in-run deduplication", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an already-in-run note and skips the duplicate in the edit call", async () => {
    // Mock editStage so the mutation doesn't actually fetch
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    // Mock validateTargets to return T1 (already in run) + T2 (new)
    vi.spyOn(sdk, "validateTargets").mockResolvedValue({
      data: {
        resolved: [
          {
            target_id: "T1",
            gene_symbol: "AAA",
            uniprot_accession: "P00001",
            canonical_key: "aaa",
          },
          {
            target_id: "T2",
            gene_symbol: "BBB",
            uniprot_accession: "P00002",
            canonical_key: "bbb",
          },
        ],
        failed: [],
      },
    } as never);

    wrap(<Stage3View data={makeData()} />);

    // Type something in the TargetValidateBox textarea and click Validate
    const textarea = screen.getByRole("textbox", { name: /add targets/i });
    await userEvent.type(textarea, "AAA\nBBB");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));

    // Wait for resolved list to appear, then click Add
    await waitFor(() => screen.getByRole("list", { name: /resolved targets/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // The note should appear, naming AAA
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/already in run/i));
    expect(screen.getByRole("status")).toHaveTextContent("AAA");

    // editStage should have been called with only the new id (T2)
    expect(editSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { analysis_id: "a1", stage: 3 },
        body: { add: ["T2"], remove: [] },
      }),
    );
    // editStage should NOT have been called with T1
    for (const call of editSpy.mock.calls) {
      expect((call[0] as { body: { add: string[] } }).body.add).not.toContain("T1");
    }
  });

  it("does not show the note when all resolved targets are new", async () => {
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    vi.spyOn(sdk, "validateTargets").mockResolvedValue({
      data: {
        resolved: [
          {
            target_id: "T3",
            gene_symbol: "CCC",
            uniprot_accession: "P00003",
            canonical_key: "ccc",
          },
        ],
        failed: [],
      },
    } as never);

    wrap(<Stage3View data={makeData()} />);

    const textarea = screen.getByRole("textbox", { name: /add targets/i });
    await userEvent.type(textarea, "CCC");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() => screen.getByRole("list", { name: /resolved targets/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(editSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          body: { add: ["T3"], remove: [] },
        }),
      ),
    );

    // No "already in run" note
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("does not call editStage when all resolved targets are duplicates", async () => {
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    vi.spyOn(sdk, "validateTargets").mockResolvedValue({
      data: {
        resolved: [
          {
            target_id: "T1",
            gene_symbol: "AAA",
            uniprot_accession: "P00001",
            canonical_key: "aaa",
          },
        ],
        failed: [],
      },
    } as never);

    wrap(<Stage3View data={makeData()} />);

    const textarea = screen.getByRole("textbox", { name: /add targets/i });
    await userEvent.type(textarea, "AAA");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() => screen.getByRole("list", { name: /resolved targets/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // Note appears
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/already in run/i));
    // editStage should NOT have been called at all
    expect(editSpy).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// D-4: Toast wiring — advance error fires notifyError; redo success fires notifyInfo
// ---------------------------------------------------------------------------

describe("Stage3View — D-4 toast wiring", () => {
  afterEach(() => vi.restoreAllMocks());

  it("fires notifyInfo with 'Re-running from step 3' when redo succeeds", async () => {
    vi.spyOn(sdk, "resetFrom").mockResolvedValue({ data: {} } as never);
    const notifyInfoSpy = vi.spyOn(toastLib, "notifyInfo").mockImplementation(() => {});

    wrap(
      <Stage3View
        data={makeRun({
          stage_state: { "3": "computed" },
          parameters: { target: { min_pchembl: 4, min_assay_confidence: 0.4 } },
        })}
      />,
    );

    // Open param panel ("Target parameters" is the ParamPanel title)
    await userEvent.click(screen.getByRole("button", { name: /target parameters/i }));
    const input = screen.getByLabelText("Minimum activity (pChEMBL)");
    await userEvent.clear(input);
    await userEvent.type(input, "6");
    await userEvent.click(screen.getByRole("button", { name: /redo from this stage/i }));

    await waitFor(() => expect(notifyInfoSpy).toHaveBeenCalledWith("Re-running from step 3"));
  });
});
