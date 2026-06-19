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

/** Get the plant-mode fieldset by its legend text. */
function plantFieldset() {
  return screen.getByRole("group", { name: /plant input mode/i });
}

/** Get the disease-mode fieldset by its legend text. */
function diseaseFieldset() {
  return screen.getByRole("group", { name: /disease input mode/i });
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
    expect(within(pf).getByRole("radio", { name: /selection/i })).toBeInTheDocument();
    expect(within(pf).getByRole("radio", { name: /manual_compounds/i })).toBeInTheDocument();
    expect(within(pf).getByRole("radio", { name: /manual_targets/i })).toBeInTheDocument();
  });

  it("renders 2 disease-mode radio options: selection, manual_disease_targets", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    const df = diseaseFieldset();
    expect(within(df).getByRole("radio", { name: /selection/i })).toBeInTheDocument();
    expect(within(df).getByRole("radio", { name: /manual_disease_targets/i })).toBeInTheDocument();
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
    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /manual_targets/i }));

    // Plant combobox should be gone
    expect(screen.queryByRole("combobox", { name: /search plants/i })).not.toBeInTheDocument();

    // Target editor (TargetValidateBox textarea) should appear with label "Plant targets"
    expect(screen.getByRole("textbox", { name: /plant targets/i })).toBeInTheDocument();

    // plant_label field should appear
    expect(screen.getByLabelText(/plant label/i)).toBeInTheDocument();
  });

  it("switching plant mode to manual_compounds shows CompoundValidateBox and plant_label, hides combobox", async () => {
    wrap(<SetupView onCreated={() => {}} />);

    await userEvent.click(
      within(plantFieldset()).getByRole("radio", { name: /manual_compounds/i }),
    );

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

    await userEvent.click(
      within(diseaseFieldset()).getByRole("radio", { name: /manual_disease_targets/i }),
    );

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
    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /manual_targets/i }));
    await userEvent.click(
      within(diseaseFieldset()).getByRole("radio", { name: /manual_disease_targets/i }),
    );

    // Validate plant targets — the plant TargetValidateBox uses label "Plant targets"
    const plantTextarea = screen.getByRole("textbox", { name: /plant targets/i });
    await userEvent.type(plantTextarea, "EGFR");
    // There are now two Validate buttons (one per TargetValidateBox); click the first
    const validateBtns = screen.getAllByRole("button", { name: /^validate$/i });
    await userEvent.click(validateBtns[0]!);
    // Wait for the resolved list from MSW
    await waitFor(() => {
      expect(screen.getAllByRole("list", { name: /resolved targets/i }).length).toBeGreaterThan(0);
    });

    // Validate disease targets
    const diseaseTextarea = screen.getByRole("textbox", { name: /disease targets/i });
    await userEvent.type(diseaseTextarea, "EGFR");
    const validateBtns2 = screen.getAllByRole("button", { name: /^validate$/i });
    await userEvent.click(validateBtns2[validateBtns2.length - 1]!);
    await waitFor(() => {
      expect(
        screen.getAllByRole("list", { name: /resolved targets/i }).length,
      ).toBeGreaterThanOrEqual(2);
    });

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

    // Mode defaults to guided
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: /mode/i })).toHaveTextContent("guided"),
    );

    // Switch plant input mode to manual_compounds to reveal CompoundValidateBox
    await userEvent.click(screen.getByRole("radio", { name: /manual_compounds/i }));

    // Type two lines into the manual compounds textarea
    await userEvent.type(screen.getByLabelText("Manual compounds"), "CCO\nNOTAKEY");

    // Click Validate
    await userEvent.click(screen.getByRole("button", { name: /validate/i }));

    // Resolved row: ethanol present
    await screen.findByText(/ethanol/i);

    // Failed row: the SMILES nudge is visible
    await screen.findByText(/SMILES/);

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
