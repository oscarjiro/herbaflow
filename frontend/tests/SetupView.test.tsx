import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { SetupView } from "../src/components/SetupView";
import "../src/lib/api";
import { server } from "./handlers";

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

test("submits a created run id", async () => {
  let createdId: string | null = null;
  render(wrap(<SetupView onCreated={(id) => (createdId = id)} />));

  await screen.findByText("Aaa bbb");
  await userEvent.selectOptions(screen.getByLabelText("Disease"), "d1");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

  await waitFor(() => expect(createdId).toBe("r1"));
});

test("defaults mode to guided, validates compounds, and sends manual_compound_ids", async () => {
  let createdId: string | null = null;
  render(wrap(<SetupView onCreated={(id) => (createdId = id)} />));

  // Mode defaults to guided
  expect((screen.getByLabelText("Mode") as HTMLSelectElement).value).toBe("guided");

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

  // Select a disease (disease section is still in selection mode)
  await waitFor(() => screen.getByLabelText("Disease"));
  await userEvent.selectOptions(screen.getByLabelText("Disease"), "d1");
  await userEvent.click(screen.getByRole("button", { name: /create analysis/i }));

  await waitFor(() => expect(createdId).toBe("r1"));
  await waitFor(() =>
    expect((captured as { manual_compound_ids?: string[] }).manual_compound_ids).toContain("c1"),
  );
});
