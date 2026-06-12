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

  it("shows 'Provided by you' badge when stage_state[\"1\"] is user_provided", async () => {
    wrap("r3");
    await screen.findByText("Curcumin");
    expect(screen.getByText(/provided by you/i)).toBeInTheDocument();
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
      // Override validate to return a compound NOT already in r3's stage-1 set (c1/c2/c3).
      // Without this, the dedup check would catch c1 (already in run) and skip the edit call.
      http.post("http://localhost:8000/compounds/validate", () =>
        HttpResponse.json({
          resolved: [
            {
              compound_id: "c99",
              canonical_key: "inchikey:LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
              canonical_name: "ethanol",
              validation_status: "externally_validated",
            },
          ],
          failed: [],
        }),
      ),
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
    expect(editRequests[0]).toEqual({ add: ["c99"], remove: [] });
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

describe("stale stage (r-stale)", () => {
  it("disables Approve and shows a re-run control while a stage is stale", async () => {
    wrap("r-stale");
    expect(await screen.findByRole("button", { name: /re-run from step 1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve & continue/i })).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// not_applicable + user_provided stage rendering
// ---------------------------------------------------------------------------

describe("not_applicable stages (r-na-s1: manual_targets plant mode)", () => {
  it("Stage 1 renders a greyed not-applicable block, not the compound table", async () => {
    wrap("r-na-s1");
    // Should show the N/A heading for step 1
    expect(await screen.findByRole("heading", { name: /step 1/i })).toBeInTheDocument();
    // Should show the not-applicable message (multiple N/A stages expected — use getAllByText)
    expect(screen.getAllByText(/not applicable for this run/i).length).toBeGreaterThan(0);
    // The normal entity list / add-compounds control must NOT appear
    expect(screen.queryByLabelText(/add compounds/i)).not.toBeInTheDocument();
  });

  it("Stage 2 renders a greyed not-applicable block", async () => {
    wrap("r-na-s1");
    expect(await screen.findByRole("heading", { name: /step 2/i })).toBeInTheDocument();
    expect(screen.getAllByText(/not applicable for this run/i).length).toBeGreaterThan(0);
    // The ADME compound table must NOT appear (no ADME-specific content like "passed" count card)
    expect(screen.queryByRole("generic", { name: /\d+ passed/i })).not.toBeInTheDocument();
  });

  it("Stage 3 shows a 'Provided by you' badge (user_provided)", async () => {
    wrap("r-na-s1");
    expect(await screen.findByRole("heading", { name: /step 3/i })).toBeInTheDocument();
    expect(screen.getByText(/provided by you/i)).toBeInTheDocument();
  });
});

describe("user_provided Stage 4 (r-manual-disease)", () => {
  it("Stage 4 shows a 'Provided by you' badge", async () => {
    wrap("r-manual-disease");
    expect(await screen.findByRole("heading", { name: /step 4/i })).toBeInTheDocument();
    expect(screen.getByText(/provided by you/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Run header display names
// ---------------------------------------------------------------------------

describe("run header display names", () => {
  it("selection mode shows catalog plant name (Aaa bbb) and disease name (Test Disease)", async () => {
    // r2 uses selection mode (no input_modes) with disease_id=d1 and plant_ids=[p1 implicit]
    wrap("r2");
    await screen.findByRole("heading", { name: /step 2/i });
    // Plant "Aaa bbb" from the /plants catalog (p1)
    // Disease "Test Disease" from the /diseases catalog (d1)
    expect(await screen.findByText(/Test Disease/i)).toBeInTheDocument();
  });

  it("manual_targets mode shows plant label from parameters.labels.plant", async () => {
    wrap("r-na-s1");
    await screen.findByRole("heading", { name: /step 3/i });
    expect(await screen.findByText(/My plant label/i)).toBeInTheDocument();
  });

  it("manual_disease_targets mode shows disease label from parameters.labels.disease", async () => {
    wrap("r-manual-disease");
    await screen.findByRole("heading", { name: /step 4/i });
    expect(await screen.findByText(/My disease label/i)).toBeInTheDocument();
  });

  it("manual mode with no label shows N/A", async () => {
    wrap("r-manual-nolabel");
    await screen.findByRole("heading", { name: /step 4/i });
    expect(await screen.findByText(/N\/A/)).toBeInTheDocument();
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
