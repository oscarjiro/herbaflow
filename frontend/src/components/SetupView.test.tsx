import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { SetupView } from "./SetupView";
import * as sdk from "../api/sdk.gen";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

/** Get the plant-mode fieldset by its legend text. */
function plantFieldset() {
  return screen.getByRole("group", { name: /plant input mode/i });
}

/** Get the disease-mode fieldset by its legend text. */
function diseaseFieldset() {
  return screen.getByRole("group", { name: /disease input mode/i });
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
  it("shows plant multiselect in default selection mode", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    // plant filter should be visible in default mode
    expect(screen.getByPlaceholderText(/filter plants/i)).toBeInTheDocument();
    // plant_label field should NOT be visible in selection mode
    expect(screen.queryByLabelText(/plant label/i)).not.toBeInTheDocument();
  });

  it("switching plant mode to manual_targets hides plant multiselect and shows target editor + plant_label", async () => {
    wrap(<SetupView onCreated={() => {}} />);

    // Switch to manual_targets
    await userEvent.click(within(plantFieldset()).getByRole("radio", { name: /manual_targets/i }));

    // Plant filter / multiselect should be gone
    expect(screen.queryByPlaceholderText(/filter plants/i)).not.toBeInTheDocument();

    // Target editor (TargetValidateBox textarea) should appear with label "Plant targets"
    expect(screen.getByRole("textbox", { name: /plant targets/i })).toBeInTheDocument();

    // plant_label field should appear
    expect(screen.getByLabelText(/plant label/i)).toBeInTheDocument();
  });

  it("switching plant mode to manual_compounds shows CompoundValidateBox and plant_label, hides multiselect", async () => {
    wrap(<SetupView onCreated={() => {}} />);

    await userEvent.click(
      within(plantFieldset()).getByRole("radio", { name: /manual_compounds/i }),
    );

    expect(screen.queryByPlaceholderText(/filter plants/i)).not.toBeInTheDocument();
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
  it("shows disease single-select in default selection mode", async () => {
    wrap(<SetupView onCreated={() => {}} />);
    const select = screen.getByRole("combobox", { name: /disease/i });
    expect(select).toBeInTheDocument();
    // disease_label should NOT be visible
    expect(screen.queryByLabelText(/disease label/i)).not.toBeInTheDocument();
  });

  it("switching disease mode to manual_disease_targets hides select and shows target editor + disease_label", async () => {
    wrap(<SetupView onCreated={() => {}} />);

    await userEvent.click(
      within(diseaseFieldset()).getByRole("radio", { name: /manual_disease_targets/i }),
    );

    // Disease select should be gone
    expect(screen.queryByRole("combobox", { name: /disease/i })).not.toBeInTheDocument();

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
  beforeEach(() => {
    vi.restoreAllMocks();
  });

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

    // Wait for plants + diseases to load from MSW
    await waitFor(() => screen.getByRole("checkbox", { name: /aaa bbb/i }));
    await waitFor(() => screen.getByText("Test Disease"));

    // Select a disease
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /disease/i }), "d1");

    // Check a plant
    await userEvent.click(screen.getByRole("checkbox", { name: /aaa bbb/i }));

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
