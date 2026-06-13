import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Stage3View } from "./Stage3View";
import * as sdk from "../../api/sdk.gen";
import type { AnalysisRead } from "../../api/types.gen";

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

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

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests
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
            { target_id: "t1", canonical_name: "PPARG", tag: "computed" },
            { target_id: "t2", canonical_name: "TP53", tag: "user-removed" },
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
    expect(screen.getByRole("button", { name: "Remove PPARG" })).toBeInTheDocument();
  });
});

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
    wrap(<Stage3View data={makeUserProvidedData()} />);
    const link = screen.getByRole("link", { name: "P31749" });
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P31749/entry");
  });
});
