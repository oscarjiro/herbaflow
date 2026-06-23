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
      onApprove={() => {}}
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
      onApprove={() => {}}
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
