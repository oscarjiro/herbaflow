import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Stage1View } from "./Stage1View";
import * as sdk from "../../api/sdk.gen";
import * as toastLib from "../../lib/toast";
import type { AnalysisRead } from "../../api/types.gen";

// ---------------------------------------------------------------------------
// Fixture helpers
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

function compoundsTable(container: HTMLElement) {
  const el = container.querySelector(".table-wrapper");
  if (!el) throw new Error("compounds table not found");
  return within(el as HTMLElement);
}

function blobToText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
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

  it("renders compounds in the shared table without a separate source column", () => {
    const { container } = wrap(
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

    const table = compoundsTable(container);
    expect(table.getByRole("table")).toBeInTheDocument();
    expect(table.getByText(/curcumin/i)).toBeInTheDocument();
    expect(table.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    expect(table.queryByText("User-curated")).not.toBeInTheDocument();
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

  it("shows a success toast after a compound add is committed", async () => {
    vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);
    const notifySuccessSpy = vi.spyOn(toastLib, "notifySuccess").mockImplementation(() => {});

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

    await waitFor(() => expect(notifySuccessSpy).toHaveBeenCalledWith("Added 1 compound"));
  });
});

// ---------------------------------------------------------------------------
// Column spec — new DataTable columns
// ---------------------------------------------------------------------------

describe("Stage1View — column spec", () => {
  it("downloads compounds with the bare CSV slug", () => {
    wrap(<Stage1View data={makeRun()} />);
    const link = screen.getByRole("link", { name: /download csv/i });
    expect(link).toHaveAttribute("download", "compounds.csv");
  });

  it("renders summary cards for total compounds and selected plants with editorial numbers", () => {
    wrap(
      <Stage1View
        data={makeRun({
          parameters: {
            input_modes: { plant: "selection", disease: "selection" },
            plant_ids: ["p1", "p2"],
          },
          stage_results: {
            "1": {
              count: 3,
              compounds: [
                { compound_id: "c1", canonical_name: "Curcumin", tag: "computed" },
                { compound_id: "c2", canonical_name: "Quercetin", tag: "computed" },
                { compound_id: "c3", canonical_name: "Berberine", tag: "computed" },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    const compoundsCard = screen.getByText("Total compounds").closest("div");
    const plantsCard = screen.getByText("Selected plants").closest("div");

    expect(compoundsCard).not.toBeNull();
    expect(plantsCard).not.toBeNull();
    expect(within(compoundsCard as HTMLElement).getByText("3")).toHaveClass("font-display");
    expect(within(plantsCard as HTMLElement).getByText("2")).toHaveClass("font-display");
  });

  it("links InChIKey through the persisted source_url when present", () => {
    wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  inchikey: "VHYFNPMBLIVWCW-UHFFFAOYSA-N",
                  source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/969516",
                  tag: "computed",
                },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    const link = screen.getByRole("link", { name: /VHYFNPMBLIVWCW-UHFFFAOYSA-N/i });
    expect(link).toHaveAttribute("href", "https://pubchem.ncbi.nlm.nih.gov/compound/969516");
    expect(link).not.toHaveAttribute("href", expect.stringContaining("#query"));
  });

  it("does not render a KNApSAcK source chip for a computed compound", () => {
    const { container } = wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  inchikey: "CURCUMIN-KEY",
                  tag: "computed",
                  source_url: "https://knapsack.jp/compound/C00001",
                },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    const table = compoundsTable(container);
    expect(table.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    expect(table.queryByText("KNApSAcK")).not.toBeInTheDocument();
    expect(table.queryByRole("link", { name: /^Curcumin$/ })).not.toBeInTheDocument();
    expect(table.getByRole("link", { name: /curcumin-key/i })).toHaveAttribute(
      "href",
      "https://knapsack.jp/compound/C00001",
    );
  });

  it("does not render a User-curated source chip for a user-added compound", () => {
    const { container } = wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  tag: "user-added",
                },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    const table = compoundsTable(container);
    expect(table.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    expect(table.queryByText("User-curated")).not.toBeInTheDocument();
  });

  it("plant-source column is ABSENT for single-plant selection mode", () => {
    wrap(
      <Stage1View
        data={makeRun({
          parameters: {
            input_modes: { plant: "selection", disease: "selection" },
            plant_ids: ["p1"],
          },
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  tag: "computed",
                },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    expect(screen.queryByRole("columnheader", { name: /plant source/i })).not.toBeInTheDocument();
  });

  it("plant-source column is ABSENT for manual_compounds mode even with per_plant", () => {
    wrap(
      <Stage1View
        data={makeRun({
          parameters: {
            input_modes: { plant: "manual_compounds", disease: "selection" },
            plant_ids: [],
          },
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  tag: "computed",
                },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    expect(screen.queryByRole("columnheader", { name: /plant source/i })).not.toBeInTheDocument();
  });

  it("plant-source column IS present for multi-plant selection mode", () => {
    wrap(
      <Stage1View
        data={makeRun({
          parameters: {
            input_modes: { plant: "selection", disease: "selection" },
            plant_ids: ["p1", "p2"],
          },
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  tag: "computed",
                },
              ],
              per_plant: { p1: ["c1"] },
              state: "computed",
            },
          },
        })}
      />,
    );

    expect(screen.getByRole("columnheader", { name: /plant source/i })).toBeInTheDocument();
  });

  it("delete button is enabled above the floor and carries the correct aria-label", () => {
    // Stage1View renders one delete button per visible row. When count > 1,
    // the button is enabled and labelled "Remove <name>", proving the existing
    // handleRemove(id) path is wired — the same path proven disabled at the floor
    // by the "disables the remove button at the one-entity floor" test above.
    wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 2,
              compounds: [
                { compound_id: "c1", canonical_name: "Curcumin", tag: "computed" },
                { compound_id: "c2", canonical_name: "Berberine", tag: "computed" },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    const removeBtn = screen.getByRole("button", { name: /remove curcumin/i });
    expect(removeBtn).toBeEnabled();
    expect(removeBtn).not.toHaveAttribute("title");
  });
});

// ---------------------------------------------------------------------------
// CSV spec
// ---------------------------------------------------------------------------

describe("Stage1View — CSV", () => {
  it("CSV header matches the column spec exactly", async () => {
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      capturedBlob = blob as Blob;
      return "blob:mock";
    });

    wrap(<Stage1View data={makeRun()} />);
    await waitFor(() => expect(capturedBlob).not.toBeNull());
    if (capturedBlob == null) throw new Error("expected CSV blob to be created");

    const csv = await blobToText(capturedBlob);
    const header = csv.split("\n")[0];
    expect(header).toBe("inchikey,name,smiles,plant_sources,source_url");
  });

  it("CSV row contains correct field values for a computed compound", async () => {
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      capturedBlob = blob as Blob;
      return "blob:mock";
    });

    wrap(
      <Stage1View
        data={makeRun({
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  inchikey: "VHYFNPMBLIVWCW-UHFFFAOYSA-N",
                  smiles: "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O",
                  source_url: "https://knapsack.jp/compound/C00001",
                  tag: "computed",
                },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    await waitFor(() => expect(capturedBlob).not.toBeNull());
    if (capturedBlob == null) throw new Error("expected CSV blob to be created");

    const csv = await blobToText(capturedBlob);
    expect(csv).toContain("VHYFNPMBLIVWCW-UHFFFAOYSA-N");
    expect(csv).toContain("Curcumin");
    expect(csv).toContain("https://knapsack.jp/compound/C00001");
    expect(csv).not.toContain("KNApSAcK");
  });

  it("CSV plant_sources column is empty string in single-plant mode", async () => {
    let capturedBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      capturedBlob = blob as Blob;
      return "blob:mock";
    });

    wrap(
      <Stage1View
        data={makeRun({
          parameters: {
            input_modes: { plant: "selection", disease: "selection" },
            plant_ids: ["p1"],
          },
          stage_results: {
            "1": {
              count: 1,
              compounds: [
                {
                  compound_id: "c1",
                  canonical_name: "Curcumin",
                  inchikey: "VHYFNPMBLIVWCW-UHFFFAOYSA-N",
                  tag: "computed",
                },
              ],
              state: "computed",
            },
          },
        })}
      />,
    );

    await waitFor(() => expect(capturedBlob).not.toBeNull());
    if (capturedBlob == null) throw new Error("expected CSV blob to be created");

    const csv = await blobToText(capturedBlob);
    const rows = csv.split("\n");
    // Data row: inchikey,name,smiles,plant_sources,source_url
    // plant_sources should be empty (not a multi-plant selection run)
    const dataRow = rows[1];
    expect(dataRow).toBeDefined();
    // The plant_sources field is between smiles and source_url — should be empty.
    // Row format: inchikey,name,smiles,,source_url
    expect(dataRow).toContain(",,");
  });
});
