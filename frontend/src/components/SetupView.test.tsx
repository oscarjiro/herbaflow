import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SetupView } from "./SetupView";
import * as sdk from "../api/sdk.gen";
import { server } from "../../tests/handlers";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// Unmount + clear any Radix portal nodes left in document.body between tests so a
// stale combobox/popover from one test cannot leak into the next, and restore
// any SDK spies so a mocked createAnalysis does not bleed into the MSW-driven tests.
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Get the plant-mode segmented control by its aria-label. */
function plantFieldset() {
  return screen.getByRole("radiogroup", { name: /plant input mode/i });
}

/** Get the disease-mode segmented control by its aria-label. */
function diseaseFieldset() {
  return screen.getByRole("radiogroup", { name: /disease input mode/i });
}

/**
 * Open the EntitySearchCombobox for the given ariaLabel and pick an option by text.
 * Waits for the option to appear in the command list before clicking it.
 */
async function pickComboOption(ariaLabel: string, optionText: string | RegExp) {
  await userEvent.click(screen.getByRole("combobox", { name: ariaLabel }));
  // Scope to the command-list options so a matching selected-chip never wins the lookup.
  const options = await screen.findAllByRole("option");
  const match = options.find((el) => {
    const text = el.textContent ?? "";
    return typeof optionText === "string" ? text.includes(optionText) : optionText.test(text);
  });
  if (!match) throw new Error(`No combobox option matching ${optionText}`);
  await userEvent.click(match);
}

// ---------------------------------------------------------------------------
// Tests — input-mode radios
// ---------------------------------------------------------------------------

describe("SetupView — plant input-mode radios", () => {
  it("renders 3 plant-mode radio options: selection, manual_compounds, manual_targets", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    const pf = plantFieldset();
    expect(within(pf).getByRole("radio", { name: /select plants/i })).toBeInTheDocument();
    expect(within(pf).getByRole("radio", { name: /enter compounds/i })).toBeInTheDocument();
    expect(within(pf).getByRole("radio", { name: /enter targets/i })).toBeInTheDocument();
  });

  it("renders 2 disease-mode radio options: selection, manual_disease_targets", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    const df = diseaseFieldset();
    expect(within(df).getByRole("radio", { name: /select disease/i })).toBeInTheDocument();
    expect(within(df).getByRole("radio", { name: /enter targets/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — plant mode switching
// ---------------------------------------------------------------------------

describe("SetupView — plant mode controls", () => {
  it("shows plant combobox trigger in default selection mode", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    // The plant combobox trigger button is present
    expect(screen.getByRole("combobox", { name: /search plants/i })).toBeInTheDocument();
    // plant_label field should NOT be visible in selection mode
    expect(screen.queryByLabelText(/plant label/i)).not.toBeInTheDocument();
  });

  it("switching plant mode to manual_targets hides plant combobox and shows target editor + plant_label", async () => {
    wrap(<SetupView onCreated={() => {}} />);

    // Switch to manual_targets
    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /enter targets/i }));

    // Plant combobox should be gone
    expect(screen.queryByRole("combobox", { name: /search plants/i })).not.toBeInTheDocument();

    // Target editor (TargetValidateBox textarea) should appear with label "Plant targets"
    expect(screen.getByRole("textbox", { name: /plant targets/i })).toBeInTheDocument();

    // plant_label field should appear
    expect(screen.getByLabelText(/plant label/i)).toBeInTheDocument();
  });

  it("switching plant mode to manual_compounds shows CompoundValidateBox and plant_label, hides combobox", async () => {
    wrap(<SetupView onCreated={() => {}} />);

    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /enter compounds/i }));

    expect(screen.queryByRole("combobox", { name: /search plants/i })).not.toBeInTheDocument();
    // CompoundValidateBox textarea has default label "Manual compounds"
    expect(screen.getByRole("textbox", { name: /manual compounds/i })).toBeInTheDocument();
    // plant_label
    expect(screen.getByLabelText(/plant label/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — disease mode switching
// ---------------------------------------------------------------------------

describe("SetupView — disease mode controls", () => {
  it("shows disease combobox trigger in default selection mode", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    expect(screen.getByRole("combobox", { name: /search disease/i })).toBeInTheDocument();
    // disease_label should NOT be visible
    expect(screen.queryByLabelText(/disease label/i)).not.toBeInTheDocument();
  });

  it("switching disease mode to manual_disease_targets hides combobox and shows target editor + disease_label", async () => {
    wrap(<SetupView onCreated={() => {}} />);

    await userEvent.click(within(diseaseFieldset()).getByRole("radio", { name: /enter targets/i }));

    // Disease combobox should be gone
    expect(screen.queryByRole("combobox", { name: /search disease/i })).not.toBeInTheDocument();

    // Target editor textarea for disease targets should appear
    expect(screen.getByRole("textbox", { name: /disease targets/i })).toBeInTheDocument();

    // disease_label
    expect(screen.getByLabelText(/disease label/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — create body per mode
// ---------------------------------------------------------------------------

describe("SetupView — create payload per mode", () => {
  it("default selection mode posts plant_input_mode=selection, disease_input_mode=selection with selected plant + disease ids", async () => {
    const createSpy = vi.spyOn(sdk, "createAnalysis").mockResolvedValue({
      data: {
        analysis_id: "r1",
        analysis_name: null,
        disease_id: "d1",
        mode: "auto",
        status: "pending",
        current_stage: null,
        stage_results: {},
        created_at: null,
        completed_at: null,
        expires_at: null,
        error_message: null,
      },
    } as never);

    wrap(<SetupView onCreated={() => {}} />);

    // Select a plant via the combobox — wait for "Aaa bbb" to appear in dropdown
    await pickComboOption("Search plants", /aaa bbb/i);

    // Select a disease via the combobox
    await pickComboOption("Search disease", /test disease/i);

    // Submit
    await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

    await waitFor(() => expect(createSpy).toHaveBeenCalledOnce());
    const body = createSpy.mock.calls[0]![0].body;
    expect(body.plant_input_mode).toBe("selection");
    expect(body.disease_input_mode).toBe("selection");
    expect(body.plant_ids).toEqual(["p1"]);
    expect(body.disease_id).toBe("d1");
    expect(body.manual_compound_ids).toEqual([]);
    expect(body.manual_target_ids).toEqual([]);
    expect(body.manual_disease_target_ids).toEqual([]);
    expect(body.plant_label).toBeNull();
    expect(body.disease_label).toBeNull();
  });

  it("manual_targets + manual_disease_targets posts correct mode fields, empty plant_ids/disease_id, and resolved ids", async () => {
    const createSpy = vi.spyOn(sdk, "createAnalysis").mockResolvedValue({
      data: {
        analysis_id: "r1",
        analysis_name: null,
        disease_id: null,
        mode: "guided",
        status: "pending",
        current_stage: null,
        stage_results: {},
        created_at: null,
        completed_at: null,
        expires_at: null,
        error_message: null,
      },
    } as never);

    wrap(<SetupView onCreated={() => {}} />);

    // Switch both modes
    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /enter targets/i }));
    await userEvent.click(within(diseaseFieldset()).getByRole("radio", { name: /enter targets/i }));

    // Validate plant targets — the plant TargetValidateBox uses label "Plant targets"
    const plantTextarea = screen.getByRole("textbox", { name: /plant targets/i });
    await userEvent.type(plantTextarea, "EGFR");
    // There are now two Validate buttons (one per TargetValidateBox); click the first
    const validateBtns = screen.getAllByRole("button", { name: /^validate$/i });
    await userEvent.click(validateBtns[0]!);
    // Wait for the resolved list from MSW then click Add to commit to the pool
    await waitFor(() => {
      expect(screen.getAllByRole("list", { name: /resolved targets/i }).length).toBeGreaterThan(0);
    });
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]!);
    // Pool chip should be visible
    await screen.findByRole("list", { name: /added plant targets/i });

    // Validate disease targets
    const diseaseTextarea = screen.getByRole("textbox", { name: /disease targets/i });
    await userEvent.type(diseaseTextarea, "EGFR");
    const validateBtns2 = screen.getAllByRole("button", { name: /^validate$/i });
    await userEvent.click(validateBtns2[validateBtns2.length - 1]!);
    await waitFor(() => {
      expect(
        screen.getAllByRole("list", { name: /resolved targets/i }).length,
      ).toBeGreaterThanOrEqual(1);
    });
    await userEvent.click(
      screen.getAllByRole("button", { name: /^add$/i })[
        screen.getAllByRole("button", { name: /^add$/i }).length - 1
      ]!,
    );
    // Pool chip should be visible
    await screen.findByRole("list", { name: /added disease targets/i });

    // Fill labels
    await userEvent.type(screen.getByLabelText(/plant label/i), "My Plant");
    await userEvent.type(screen.getByLabelText(/disease label/i), "My Disease");

    // Submit
    await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

    await waitFor(() => expect(createSpy).toHaveBeenCalledOnce());
    const body = createSpy.mock.calls[0]![0].body;
    expect(body.plant_input_mode).toBe("manual_targets");
    expect(body.disease_input_mode).toBe("manual_disease_targets");
    expect(body.plant_ids).toEqual([]);
    expect(body.disease_id).toBeNull();
    expect(body.manual_target_ids).toEqual(["t1"]);
    expect(body.manual_disease_target_ids).toEqual(["t1"]);
    expect(body.manual_compound_ids).toEqual([]);
    expect(body.plant_label).toBe("My Plant");
    expect(body.disease_label).toBe("My Disease");
  });
});

// ---------------------------------------------------------------------------
// Tests — end-to-end create flow (MSW handlers, no SDK spy)
// ---------------------------------------------------------------------------

describe("SetupView — end-to-end create flow", () => {
  it("submits a created run id", async () => {
    let createdId: string | null = null;
    wrap(<SetupView onCreated={(id) => (createdId = id)} />);

    // Select plant and disease via comboboxes
    await pickComboOption("Search plants", /aaa bbb/i);
    await pickComboOption("Search disease", /test disease/i);
    await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

    await waitFor(() => expect(createdId).toBe("r1"));
  });

  it("defaults mode to guided, validates compounds, and sends manual_compound_ids", async () => {
    let createdId: string | null = null;
    wrap(<SetupView onCreated={(id) => (createdId = id)} />);

    // Mode defaults to guided — now rendered as radio cards
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /guided/i })).toHaveAttribute(
        "aria-checked",
        "true",
      ),
    );

    // Switch plant input mode to manual_compounds to reveal CompoundValidateBox
    await userEvent.click(screen.getByRole("radio", { name: /enter compounds/i }));

    // Type two lines into the manual compounds textarea
    await userEvent.type(screen.getByLabelText("Manual compounds"), "CCO\nNOTAKEY");

    // Click Validate
    await userEvent.click(screen.getByRole("button", { name: /validate/i }));

    // Resolved row: ethanol present in the validate-box resolved list
    await screen.findByText(/ethanol/i);

    // Failed row: expand the collapsed invalid-inputs control then check the SMILES nudge
    const invalidBtn = await screen.findByRole("button", { name: /invalid input/i });
    await userEvent.click(invalidBtn);
    await screen.findByText(/SMILES/);

    // Click Add to commit the resolved batch to the pool
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    // The pool chip for ethanol should appear
    await screen.findByRole("list", { name: /added compounds/i });

    // Now complete a create: override the handler to capture the body
    let captured: unknown = null;
    server.use(
      http.post("http://localhost:8000/analyses", async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json(
          {
            analysis_id: "r1",
            analysis_name: null,
            disease_id: "d1",
            mode: "guided",
            status: "pending",
            current_stage: null,
            stage_results: {},
            created_at: null,
            completed_at: null,
            expires_at: null,
            error_message: null,
          },
          { status: 202 },
        );
      }),
    );

    // Select a disease via the new combobox
    await pickComboOption("Search disease", /test disease/i);
    await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

    await waitFor(() => expect(createdId).toBe("r1"));
    await waitFor(() =>
      expect((captured as { manual_compound_ids?: string[] }).manual_compound_ids).toContain("c1"),
    );
  });
});

// ---------------------------------------------------------------------------
// Tests — added-pool accumulation, dedup, remove, mode-switch persistence
// ---------------------------------------------------------------------------

describe("SetupView — manual setup added-pool", () => {
  /** Validate in the compound box and click Add to commit to the pool. */
  async function validateAndAddCompounds() {
    await userEvent.type(screen.getByLabelText("Manual compounds"), "CCO");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    // Wait for the validate-box resolved list
    await screen.findByText(/ethanol/i);
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    // Pool should now show
    await screen.findByRole("list", { name: /added compounds/i });
  }

  it("compound pool: validate + Add accumulates; second Add of same item does not duplicate", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    await userEvent.click(screen.getByRole("radio", { name: /enter compounds/i }));

    // First Add — MSW always resolves to c1/ethanol
    await validateAndAddCompounds();
    expect(
      within(screen.getByRole("list", { name: /added compounds/i })).getAllByRole("listitem"),
    ).toHaveLength(1);

    // Second validate + Add of the same item — should not duplicate
    await userEvent.type(screen.getByLabelText("Manual compounds"), "CCO");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    // Scope to the validate-box resolved list to avoid ambiguity with the pool chip
    await waitFor(() => {
      expect(
        within(screen.getByRole("list", { name: /resolved compounds/i })).getByText(/ethanol/i),
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // Still one item in the pool
    await waitFor(() => {
      expect(
        within(screen.getByRole("list", { name: /added compounds/i })).getAllByRole("listitem"),
      ).toHaveLength(1);
    });
  });

  it("compound pool: Remove button removes just that item", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    await userEvent.click(screen.getByRole("radio", { name: /enter compounds/i }));
    await validateAndAddCompounds();

    // Chip is present
    const pool = screen.getByRole("list", { name: /added compounds/i });
    expect(within(pool).getAllByRole("listitem")).toHaveLength(1);

    // Click Remove
    await userEvent.click(within(pool).getByRole("button", { name: /remove/i }));

    // Pool list should be gone (no items → not rendered)
    await waitFor(() => {
      expect(screen.queryByRole("list", { name: /added compounds/i })).not.toBeInTheDocument();
    });
  });

  it("compound pool: submit sends the accumulated compound ids", async () => {
    const createSpy = vi.spyOn(sdk, "createAnalysis").mockResolvedValue({
      data: {
        analysis_id: "r1",
        analysis_name: null,
        disease_id: "d1",
        mode: "guided",
        status: "pending",
        current_stage: null,
        stage_results: {},
        created_at: null,
        completed_at: null,
        expires_at: null,
        error_message: null,
      },
    } as never);

    wrap(<SetupView onCreated={() => {}} />);
    await userEvent.click(screen.getByRole("radio", { name: /enter compounds/i }));
    await validateAndAddCompounds();

    // Select a disease to make form submittable
    await pickComboOption("Search disease", /test disease/i);
    await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

    await waitFor(() => expect(createSpy).toHaveBeenCalledOnce());
    const body = createSpy.mock.calls[0]![0].body;
    expect(body.manual_compound_ids).toContain("c1");
  });

  it("compound pool: switching away and back to manual_compounds keeps the pool visible", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    await userEvent.click(screen.getByRole("radio", { name: /enter compounds/i }));
    await validateAndAddCompounds();

    // Switch away — scope to plantFieldset to avoid ambiguity with the disease selection radio
    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /select plants/i }));
    expect(screen.queryByRole("list", { name: /added compounds/i })).not.toBeInTheDocument();

    // Switch back
    await userEvent.click(screen.getByRole("radio", { name: /enter compounds/i }));
    await screen.findByRole("list", { name: /added compounds/i });
    expect(
      within(screen.getByRole("list", { name: /added compounds/i })).getAllByRole("listitem"),
    ).toHaveLength(1);
  });

  it("plant target pool: validate + Add accumulates and Remove removes", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /enter targets/i }));

    await userEvent.type(screen.getByRole("textbox", { name: /plant targets/i }), "EGFR");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() =>
      expect(screen.getAllByRole("list", { name: /resolved targets/i }).length).toBeGreaterThan(0),
    );
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    await screen.findByRole("list", { name: /added plant targets/i });

    const pool = screen.getByRole("list", { name: /added plant targets/i });
    expect(within(pool).getAllByRole("listitem")).toHaveLength(1);

    // Remove
    await userEvent.click(within(pool).getByRole("button", { name: /remove/i }));
    await waitFor(() => {
      expect(screen.queryByRole("list", { name: /added plant targets/i })).not.toBeInTheDocument();
    });
  });

  it("disease target pool: validate + Add accumulates; switching away and back keeps pool", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    await userEvent.click(within(diseaseFieldset()).getByRole("radio", { name: /enter targets/i }));

    await userEvent.type(screen.getByRole("textbox", { name: /disease targets/i }), "EGFR");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() =>
      expect(screen.getAllByRole("list", { name: /resolved targets/i }).length).toBeGreaterThan(0),
    );
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    await screen.findByRole("list", { name: /added disease targets/i });

    // Switch away to selection
    await userEvent.click(
      within(diseaseFieldset()).getByRole("radio", { name: /select disease/i }),
    );
    expect(screen.queryByRole("list", { name: /added disease targets/i })).not.toBeInTheDocument();

    // Switch back
    await userEvent.click(within(diseaseFieldset()).getByRole("radio", { name: /enter targets/i }));
    await screen.findByRole("list", { name: /added disease targets/i });
    expect(
      within(screen.getByRole("list", { name: /added disease targets/i })).getAllByRole("listitem"),
    ).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Tests — double-submit guard
// ---------------------------------------------------------------------------

describe("SetupView — create button double-submit guard", () => {
  it("disables the Create button while the create mutation is in-flight", async () => {
    // Never resolves so the mutation stays pending throughout the test.
    vi.spyOn(sdk, "createAnalysis").mockReturnValue(new Promise(() => {}));

    wrap(<SetupView onCreated={() => {}} />);

    await pickComboOption("Search plants", /aaa bbb/i);
    await pickComboOption("Search disease", /test disease/i);

    const createBtn = screen.getByRole("button", { name: /create analysis/i });
    expect(createBtn).not.toBeDisabled();

    await userEvent.click(createBtn);
    expect(createBtn).toBeDisabled();
  });
});
