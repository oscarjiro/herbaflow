/**
 * SetupView tests — advanced parameters section.
 *
 * Covers:
 * - Section is collapsed by default (no param panels visible).
 * - Expanding the section reveals the per-group param panels.
 * - Changing a param includes it in the `parameters` field of the POST body.
 * - Leaving everything at defaults sends no `parameters` key (undefined → omitted).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { SetupView } from "../src/components/SetupView";
import { server } from "./handlers";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SetupView onCreated={() => {}} />
    </QueryClientProvider>,
  );
}

/** Helper: pick a plant via the combobox + pick a disease so the form becomes submittable. */
async function fillRequiredFields() {
  // The EntitySearchCombobox is now a direct-type input — type to open the results dropdown.
  const plantCombo = await screen.findByRole("combobox", { name: /search plants/i });
  await userEvent.type(plantCombo, "a");
  const plantOption = await screen.findByRole("option", { name: /Aaa bbb/i });
  await userEvent.click(plantOption);

  // Disease: same pattern
  const diseaseCombo = await screen.findByRole("combobox", { name: /search disease/i });
  await userEvent.type(diseaseCombo, "a");
  const diseaseOption = await screen.findByRole("option", { name: /Test Disease/i });
  await userEvent.click(diseaseOption);
}

describe("SetupView — advanced parameters section", () => {
  it("the advanced-parameters section is collapsed by default", () => {
    wrap();
    // The toggle button is present but the param group panels are not rendered.
    expect(screen.getByRole("button", { name: /advanced parameters/i })).toBeInTheDocument();
    // No group title visible before expanding.
    expect(screen.queryByText("ADME screening")).not.toBeInTheDocument();
    expect(screen.queryByText("Functional enrichment")).not.toBeInTheDocument();
  });

  it("expanding the section reveals all six group panels", async () => {
    wrap();
    await userEvent.click(screen.getByRole("button", { name: /advanced parameters/i }));
    expect(screen.getByText("ADME screening")).toBeInTheDocument();
    expect(screen.getByText("Target identification")).toBeInTheDocument();
    expect(screen.getByText("Disease targets")).toBeInTheDocument();
    expect(screen.getByText("PPI network")).toBeInTheDocument();
    expect(screen.getByText("Hub genes")).toBeInTheDocument();
    expect(screen.getByText("Functional enrichment")).toBeInTheDocument();
  });

  it("clicking the toggle a second time collapses the section again", async () => {
    wrap();
    const toggle = screen.getByRole("button", { name: /advanced parameters/i });
    await userEvent.click(toggle);
    expect(screen.getByText("ADME screening")).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.queryByText("ADME screening")).not.toBeInTheDocument();
  });

  it("changing a param includes it in the POST body under the correct group key", async () => {
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("http://localhost:8000/analyses", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
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
          { status: 202 },
        );
      }),
    );

    wrap();

    // Fill required fields first so the form is submittable.
    await fillRequiredFields();

    // Expand advanced parameters and open the ADME group panel.
    await userEvent.click(screen.getByRole("button", { name: /advanced parameters/i }));
    // Open the ADME screening ParamPanel (it's collapsed by default).
    await userEvent.click(screen.getByRole("button", { name: /adme screening/i }));

    // Change max_mw to a non-default value (default = 500).
    // The field renders via its humanized label from labels.ts.
    const maxMwInput = screen.getByLabelText("Max molecular weight (Da)");
    await userEvent.clear(maxMwInput);
    await userEvent.type(maxMwInput, "600");

    // Submit.
    await userEvent.click(screen.getByRole("button", { name: /start analysis/i }));

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
    });

    // The POST body must carry parameters.adme.max_mw = 600.
    const params = capturedBody!["parameters"] as
      | Record<string, Record<string, unknown>>
      | undefined;
    expect(params).toBeDefined();
    const adme = params?.["adme"];
    expect(adme).toBeDefined();
    expect(adme?.["max_mw"]).toBe(600);
  });

  it("leaving all params at defaults sends no parameters field (undefined omitted)", async () => {
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("http://localhost:8000/analyses", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
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
          { status: 202 },
        );
      }),
    );

    wrap();

    await fillRequiredFields();

    // Submit without touching any advanced parameter.
    await userEvent.click(screen.getByRole("button", { name: /start analysis/i }));

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
    });

    // parameters must be absent (JSON.stringify omits undefined values).
    const body = capturedBody!;
    expect(body["parameters"]).toBeUndefined();
  });
});
