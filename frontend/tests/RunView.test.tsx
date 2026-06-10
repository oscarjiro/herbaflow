import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, test, vi } from "vitest";
import { RunView } from "../src/components/RunView";
import "../src/lib/api";
import { server } from "./handlers";

function wrap(analysisId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RunView analysisId={analysisId} />
    </QueryClientProvider>,
  );
}

test("renders the stage 1 compound list", async () => {
  wrap("r1");
  expect(await screen.findByText("Alpha")).toBeInTheDocument();
  expect(await screen.findByText(/status: complete/i)).toBeInTheDocument();
});

describe("RunView with Stage 2 data", () => {
  it("renders Stage 2 view when stage_results['2'] is present", async () => {
    wrap("r2");
    // Stage 2 section header appears once data loads
    expect(await screen.findByRole("heading", { name: /step 2/i })).toBeInTheDocument();
    // Compound names appear in the table (may appear multiple times across stage1 list + table)
    const curcuminEls = await screen.findAllByText("Curcumin");
    expect(curcuminEls.length).toBeGreaterThan(0);
  });

  it("shows exactly one ApprovalBar at stage_2_awaiting_approval", async () => {
    wrap("r2");
    // Wait for data to load — heading is a reliable marker
    await screen.findByRole("heading", { name: /step 2/i });
    // Only the per-stage (Stage 2) bar may show; RunView's own bar is gated to
    // Stage 1, so an awaiting Stage 2 must render a single Approve button.
    const approveBtns = screen.getAllByRole("button", { name: /approve/i });
    expect(approveBtns).toHaveLength(1);
  });

  it("does NOT show approve button for r1 which is complete", async () => {
    wrap("r1");
    await screen.findByText("Alpha");
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });
});

describe("Step-1 in-stage compound editor (r3: stage_1_awaiting_approval)", () => {
  it("renders tagged compounds with user-removed shown as struck/greyed", async () => {
    wrap("r3");
    // All compounds are rendered
    expect(await screen.findByText("Curcumin")).toBeInTheDocument();
    expect(await screen.findByText("Berberine")).toBeInTheDocument();
    expect(await screen.findByText("RemovedOne")).toBeInTheDocument();
    // The user-removed compound has the visual treatment class
    const removedEl = screen.getByText("RemovedOne");
    expect(removedEl.closest("li")).toHaveClass("entity-row--removed");
  });

  it("shows 'edited' indicator when stage state is user_provided", async () => {
    wrap("r3");
    await screen.findByText("Curcumin");
    expect(screen.getByText(/edited/i)).toBeInTheDocument();
  });

  it("clicking Remove calls editStage with remove body and refetches", async () => {
    const editRequests: unknown[] = [];

    wrap("r3");
    // Wait for initial data — Curcumin from default r3 handler
    await screen.findByText("Curcumin");

    // Now override: after Remove is clicked, the POST and subsequent GET return post-remove state
    const postRemoveState = {
      analysis_id: "r3",
      analysis_name: null,
      disease_id: "d1",
      mode: "guided",
      status: "stage_1_awaiting_approval",
      current_stage: 1,
      parameters: {},
      stage_results: {
        "1": {
          count: 1,
          compounds: [{ compound_id: "c2", canonical_name: "Berberine", tag: "computed" }],
          per_plant: {},
          state: "user_provided",
        },
      },
      created_at: null,
      completed_at: null,
      expires_at: null,
      error_message: null,
    };
    server.use(
      http.post("http://localhost:8000/analyses/r3/stages/1/edit", async ({ request }) => {
        editRequests.push(await request.json());
        return HttpResponse.json(postRemoveState);
      }),
      // After invalidation the GET refetch returns the post-remove state
      http.get("http://localhost:8000/analyses/r3", () => HttpResponse.json(postRemoveState)),
    );

    await userEvent.click(screen.getByRole("button", { name: /remove curcumin/i }));

    await waitFor(() => expect(editRequests).toHaveLength(1));
    expect(editRequests[0]).toEqual({ add: [], remove: ["c1"] });
    // After refetch, Curcumin is gone and Berberine is still shown
    await waitFor(() => expect(screen.queryByText("Curcumin")).not.toBeInTheDocument());
    expect(screen.getByText("Berberine")).toBeInTheDocument();
  });

  it("adding via validate box calls editStage with add body", async () => {
    const editRequests: unknown[] = [];
    server.use(
      http.post("http://localhost:8000/analyses/r3/stages/1/edit", async ({ request }) => {
        editRequests.push(await request.json());
        return HttpResponse.json({
          analysis_id: "r3",
          analysis_name: null,
          disease_id: "d1",
          mode: "guided",
          status: "stage_1_awaiting_approval",
          current_stage: 1,
          parameters: {},
          stage_results: {
            "1": {
              count: 3,
              compounds: [
                { compound_id: "c1", canonical_name: "Curcumin", tag: "computed" },
                { compound_id: "c2", canonical_name: "Berberine", tag: "user-added" },
                { compound_id: "c99", canonical_name: "ethanol", tag: "user-added" },
              ],
              per_plant: {},
              state: "user_provided",
            },
          },
          created_at: null,
          completed_at: null,
          expires_at: null,
          error_message: null,
        });
      }),
    );

    wrap("r3");
    await screen.findByText("Curcumin");

    // Type into the add compounds textarea and validate
    const addTextarea = screen.getByLabelText(/add compounds/i);
    await userEvent.type(addTextarea, "CCO");
    await userEvent.click(screen.getByRole("button", { name: /validate/i }));

    // Wait for resolved result to appear, then click Add
    await screen.findByText(/ethanol/i);
    // The validated compound should have an "Add" button in the Stage1 context
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => expect(editRequests).toHaveLength(1));
    expect(editRequests[0]).toEqual({ add: ["c1"], remove: [] });
  });
});

describe("Step-1 cap enforcement (r4: count at 2000)", () => {
  it("shows cap/current message and disables the add control when at cap", async () => {
    wrap("r4");
    await screen.findByText("Curcumin");
    // The count/cap display should be visible
    expect(screen.getByText(/2000\s*\/\s*2000/)).toBeInTheDocument();
    // The validate textarea in the add control should be disabled
    const addTextarea = screen.getByLabelText(/add compounds/i);
    expect(addTextarea).toBeDisabled();
  });
});

describe("empty Stage 4 checkpoint (r-empty4)", () => {
  it("shows the Approve button disabled at an empty stage", async () => {
    wrap("r-empty4");
    await screen.findByRole("heading", { name: /step 4/i });
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
  });
});

describe("failed run recovery (r-failed)", () => {
  it("shows a Back to setup button that calls onReset", async () => {
    const onReset = vi.fn();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <RunView analysisId="r-failed" onReset={onReset} />
      </QueryClientProvider>,
    );
    const btn = await screen.findByRole("button", { name: /back to setup/i });
    await userEvent.click(btn);
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
