import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AnalysisRead } from "@/api/types.gen";
import { StageView } from "./StageView";

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
