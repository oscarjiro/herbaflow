import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AnalysisRead } from "@/api/types.gen";
import { StageView } from "./StageView";
import { Stage5View } from "./Stage5View";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const base = (over: Partial<AnalysisRead>): AnalysisRead =>
  ({
    analysis_id: "a",
    status: "stage_3_awaiting_approval",
    current_stage: 3,
    stage_results: { "3": { count: 12 } },
    stage_state: {},
    ...over,
  }) as AnalysisRead;

function renderStage(data: AnalysisRead) {
  return wrap(
    <StageView
      data={data}
      stage={3}
      title="Targets"
      kicker="03 · Targets"
      onApprove={() => Promise.resolve()}
      approvePending={false}
    >
      <div data-testid="slot">table goes here</div>
    </StageView>,
  );
}

test("completed state renders the title as h1 and mounts the content slot", () => {
  renderStage(base({}));
  expect(screen.getByRole("heading", { level: 1, name: "Targets" })).toBeInTheDocument();
  expect(screen.getByTestId("slot")).toBeInTheDocument();
});

test("running state shows a progress count and hides the content slot", () => {
  renderStage(
    base({
      status: "stage_3_running",
      stage_results: {},
      progress: { stage: 3, processed: 4, total: 10 },
    }),
  );
  expect(screen.getByText(/4\s*\/\s*10/)).toBeInTheDocument();
  expect(screen.queryByTestId("slot")).toBeNull();
});

test("stage-3 running with progress renders gradient fill at processed/total width and 'Working' label", () => {
  renderStage(
    base({
      status: "stage_3_running",
      stage_results: {},
      progress: { stage: 3, processed: 132, total: 180 },
    }),
  );
  // "Working" label is present
  expect(screen.getByText(/Working/)).toBeInTheDocument();
  // tabular count is exact
  expect(screen.getByText(/132\s*\/\s*180/)).toBeInTheDocument();
  // progress fill element carries the correct inline width (≈73.3%)
  const fill = document.querySelector(".progress-fill");
  expect(fill).not.toBeNull();
  const width = (fill as HTMLElement).style.width;
  expect(parseFloat(width)).toBeCloseTo((132 / 180) * 100, 0);
  // progressbar role is present
  expect(screen.getByRole("progressbar")).toBeInTheDocument();
  // shimmer skeleton must NOT be the mechanism here
  expect(document.querySelector(".sk")).toBeNull();
});

test("stage-1 running with no per-item progress renders shimmer skeleton (not an empty bar)", () => {
  const data: AnalysisRead = {
    analysis_id: "a",
    status: "stage_1_running",
    current_stage: 1,
    stage_results: {},
    stage_state: {},
    progress: null,
  } as unknown as AnalysisRead;

  wrap(
    <StageView
      data={data}
      stage={1}
      title="Compounds"
      kicker="01 · Compounds"
      onApprove={() => Promise.resolve()}
      approvePending={false}
    >
      <div data-testid="slot">table goes here</div>
    </StageView>,
  );

  // shimmer skeleton rows must be present
  const skRows = document.querySelectorAll(".sk");
  expect(skRows.length).toBeGreaterThan(0);
  // no gradient fill bar (no progress data available for stage 1)
  expect(document.querySelector(".progress-fill")).toBeNull();
  // content slot hidden while running
  expect(screen.queryByTestId("slot")).toBeNull();
});

test("blocked/empty state shows a no-results message and recovery", () => {
  renderStage(base({ stage_results: { "3": { count: 0 } } }));
  expect(screen.getByText(/no results/i)).toBeInTheDocument();
});

// Dedup guard: the shell is the SOLE home for the header + ApprovalBar. A wrapped
// Stage*View must not render its own duplicate (the bug this refactor removed).
const STAGE5_DATA = {
  analysis_id: "a1",
  status: "stage_5_awaiting_approval",
  current_stage: 5,
  parameters: {},
  stage_results: {
    "5": {
      overlap: [
        {
          target_id: "T1",
          gene_symbol: "EGFR",
          uniprot_accession: "P00533",
          opentargets_score: 0.8,
        },
      ],
      count: 1,
      compound_target_count: 40,
      disease_target_count: 30,
      unmapped_count: 0,
      state: "computed",
      flags: [],
    },
  },
  stage_state: {},
} as unknown as AnalysisRead;

function renderStage5Composition() {
  return wrap(
    <StageView
      data={STAGE5_DATA}
      stage={5}
      title="Shared targets"
      kicker="05 · Shared targets"
      onApprove={() => Promise.resolve()}
      approvePending={false}
    >
      <Stage5View data={STAGE5_DATA} />
    </StageView>,
  );
}

test("wrapping a stage view yields exactly one approval control (no child duplicate)", () => {
  renderStage5Composition();
  expect(screen.getAllByRole("button", { name: /approve & continue/i })).toHaveLength(1);
});

test("the shell owns the heading; the wrapped child renders no own Step heading", () => {
  renderStage5Composition();
  expect(screen.getByRole("heading", { level: 1, name: "Shared targets" })).toBeInTheDocument();
  expect(screen.queryByText("Step 5: Target Overlap")).toBeNull();
});

// ── UX-15: empty-but-addable entity stages ──────────────────────────────────

function baseRun(count: number): AnalysisRead {
  return {
    analysis_id: "a1",
    status: "stage_3_awaiting_approval",
    current_stage: 3,
    stage_results: { "3": { count } },
    stage_state: {},
    parameters: { input_modes: { plant: "selection", disease: "selection" } },
  } as unknown as AnalysisRead;
}

const noop = async () => {};

describe("StageView empty-but-addable", () => {
  it("renders children + notice (not the dead-end) when empty and addable", () => {
    wrap(
      <StageView
        data={baseRun(0)}
        stage={3}
        title="Targets"
        kicker="03"
        onApprove={noop}
        approvePending={false}
        canAddWhenEmpty
      >
        <div>STAGE BODY</div>
      </StageView>,
    );
    expect(screen.getByText("STAGE BODY")).toBeInTheDocument();
    expect(screen.queryByText("No results at this step.")).not.toBeInTheDocument();
    expect(screen.getByText(/no results yet/i)).toBeInTheDocument();
  });

  it("renders the dead-end when empty and NOT addable", () => {
    wrap(
      <StageView
        data={baseRun(0)}
        stage={3}
        title="Targets"
        kicker="03"
        onApprove={noop}
        approvePending={false}
        canAddWhenEmpty={false}
      >
        <div>STAGE BODY</div>
      </StageView>,
    );
    expect(screen.getByText("No results at this step.")).toBeInTheDocument();
    expect(screen.queryByText("STAGE BODY")).not.toBeInTheDocument();
  });
});

// ── failed run (e.g. reaper-killed, or a stage crash) ───────────────────────

const failedRun = {
  analysis_id: "a1",
  status: "failed",
  current_stage: 6,
  error_message: "The server restarted while this analysis was running. Please run it again.",
  stage_results: {
    "1": { count: 1 },
    "2": { count: 1 },
    "3": { count: 1 },
    "4": { count: 1 },
    "5": { count: 1 },
  },
  stage_state: {},
} as unknown as AnalysisRead;

describe("StageView — failed run", () => {
  it("shows the failure notice + re-run on the failed stage, not a blank body", () => {
    wrap(
      <StageView
        data={failedRun}
        stage={6}
        title="Protein interactions"
        kicker="06"
        onApprove={noop}
        approvePending={false}
      >
        <div data-testid="ppi-body">PPI table</div>
      </StageView>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/step 6 failed/i)).toBeInTheDocument();
    expect(screen.getByText(/server restarted/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /re-run from step 6/i })).toBeInTheDocument();
    expect(screen.queryByTestId("ppi-body")).not.toBeInTheDocument();
    // title still renders for context
    expect(
      screen.getByRole("heading", { level: 1, name: "Protein interactions" }),
    ).toBeInTheDocument();
  });

  it("still renders the body of a completed earlier stage of a failed run", () => {
    wrap(
      <StageView
        data={failedRun}
        stage={5}
        title="Overlap"
        kicker="05"
        onApprove={noop}
        approvePending={false}
      >
        <div data-testid="overlap-body">overlap table</div>
      </StageView>,
    );
    expect(screen.getByTestId("overlap-body")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
