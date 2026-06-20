import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Stage1View } from "./Stage1View";
import * as sdk from "../../api/sdk.gen";
import type { AnalysisRead } from "../../api/types.gen";

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

/** Minimal AnalysisRead whose Stage 1 compound set already contains C1/Quercetin. */
function makeRun(overrides: Partial<AnalysisRead> = {}): AnalysisRead {
  return {
    analysis_id: "a1",
    analysis_name: null,
    disease_id: "d1",
    mode: "guided",
    status: "stage_1_awaiting_approval",
    current_stage: 1,
    parameters: {},
    stage_results: {
      "1": {
        count: 1,
        compounds: [{ compound_id: "C1", canonical_name: "Quercetin", tag: "computed" }],
        state: "computed",
      },
    },
    stage_state: { "1": "computed" },
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
    ...overrides,
  };
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Badge behaviour (L-12 / F-DUP-3 fix)
// ---------------------------------------------------------------------------

describe("Stage1View — badge source (stage_state not presentational state)", () => {
  it("does not show 'Provided by you' for a computed-then-edited Stage 1", () => {
    // stage_state["1"] === "computed" but presentational state === "user_provided"
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <Stage1View
          data={
            {
              analysis_id: "x",
              analysis_name: null,
              disease_id: "d1",
              mode: "guided",
              status: "stage_1_awaiting_approval",
              current_stage: 1,
              parameters: {},
              stage_results: {
                "1": {
                  state: "user_provided",
                  count: 1,
                  compounds: [{ compound_id: "c1", canonical_name: "curcumin", tag: "user-added" }],
                },
              },
              stage_state: { "1": "computed" },
              created_at: null,
              completed_at: null,
              expires_at: null,
              error_message: null,
            } as unknown as AnalysisRead
          }
        />
      </QueryClientProvider>,
    );
    expect(screen.queryByText(/Provided by you/)).toBeNull();
  });

  it('shows exactly one \'Provided by you\' badge when stage_state["1"] === "user_provided"', () => {
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <Stage1View
          data={
            {
              analysis_id: "y",
              analysis_name: null,
              disease_id: "d1",
              mode: "guided",
              status: "stage_1_awaiting_approval",
              current_stage: 1,
              parameters: {},
              stage_results: {
                "1": {
                  state: "user_provided",
                  count: 1,
                  compounds: [{ compound_id: "c1", canonical_name: "curcumin", tag: "user-added" }],
                },
              },
              stage_state: { "1": "user_provided" },
              created_at: null,
              completed_at: null,
              expires_at: null,
              error_message: null,
            } as unknown as AnalysisRead
          }
        />
      </QueryClientProvider>,
    );
    // Exactly one "Provided by you" badge
    const badges = screen.getAllByText(/Provided by you/);
    expect(badges).toHaveLength(1);
    // No separate "edited" badge
    expect(screen.queryByText(/edited/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Stage1View — already-in-run deduplication", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("hides compounds tagged user-removed", () => {
    wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 2,
              compounds: [
                { compound_id: "c1", canonical_name: "Berberine", tag: "user-removed" },
                { compound_id: "c2", canonical_name: "Curcumin", tag: "computed" },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText(/curcumin/i)).toBeInTheDocument();
    expect(screen.queryByText(/berberine/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /remove berberine/i })).toBeNull();
  });

  it("disables the remove button at the one-entity floor and uses the floor title", () => {
    wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 1,
              compounds: [{ compound_id: "c1", canonical_name: "Quercetin", tag: "computed" }],
              state: "computed",
            },
          },
        })}
      />,
    );

    const removeButton = screen.getByRole("button", { name: /remove quercetin/i });
    expect(removeButton).toBeDisabled();
    expect(removeButton).toHaveAttribute("title", "A stage must keep at least one entry.");
  });

  it("renders compounds in the shared table with a provenance chip and an in-table delete", () => {
    wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 1,
              compounds: [{ compound_id: "c1", canonical_name: "curcumin", tag: "user-added" }],
              state: "computed",
            },
          },
        })}
      />,
    );

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText(/curcumin/i)).toBeInTheDocument();
    expect(screen.getByText("Added by you")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove curcumin/i })).toBeInTheDocument();
  });

  it("shows an already-in-run note and skips the duplicate in the edit call", async () => {
    // Mock editStage so the mutation doesn't actually fetch
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    // Mock validateCompounds to return C1 (already in run) + C2 (new)
    vi.spyOn(sdk, "validateCompounds").mockResolvedValue({
      data: {
        resolved: [
          { compound_id: "C1", canonical_name: "Quercetin", canonical_key: "quercetin" },
          { compound_id: "C2", canonical_name: "Kaempferol", canonical_key: "kaempferol" },
        ],
        failed: [],
      },
    } as never);

    wrap(<Stage1View data={makeRun()} />);

    // Type something in the CompoundValidateBox textarea and click Validate
    const textarea = screen.getByRole("textbox", { name: /add compounds/i });
    await userEvent.type(textarea, "Quercetin\nKaempferol");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));

    // Wait for resolved list to appear, then click Add
    await waitFor(() => screen.getByRole("list", { name: /resolved compounds/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // The note should appear, naming Quercetin
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/already in run/i));
    expect(screen.getByRole("status")).toHaveTextContent("Quercetin");

    // editStage should have been called with only the new id (C2)
    expect(editSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { analysis_id: "a1", stage: 1 },
        body: { add: ["C2"], remove: [] },
      }),
    );
    // editStage should NOT have been called with C1
    for (const call of editSpy.mock.calls) {
      expect((call[0] as { body: { add: string[] } }).body.add).not.toContain("C1");
    }
  });

  it("does not show the note when all resolved compounds are new", async () => {
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    vi.spyOn(sdk, "validateCompounds").mockResolvedValue({
      data: {
        resolved: [{ compound_id: "C3", canonical_name: "Rutin", canonical_key: "rutin" }],
        failed: [],
      },
    } as never);

    wrap(<Stage1View data={makeRun()} />);

    const textarea = screen.getByRole("textbox", { name: /add compounds/i });
    await userEvent.type(textarea, "Rutin");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() => screen.getByRole("list", { name: /resolved compounds/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(editSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          body: { add: ["C3"], remove: [] },
        }),
      ),
    );

    // No "already in run" note
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("does not call editStage when all resolved compounds are duplicates", async () => {
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    vi.spyOn(sdk, "validateCompounds").mockResolvedValue({
      data: {
        resolved: [{ compound_id: "C1", canonical_name: "Quercetin", canonical_key: "quercetin" }],
        failed: [],
      },
    } as never);

    wrap(<Stage1View data={makeRun()} />);

    const textarea = screen.getByRole("textbox", { name: /add compounds/i });
    await userEvent.type(textarea, "Quercetin");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() => screen.getByRole("list", { name: /resolved compounds/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // Note appears
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/already in run/i));
    // editStage should NOT have been called at all
    expect(editSpy).not.toHaveBeenCalled();
  });
});
