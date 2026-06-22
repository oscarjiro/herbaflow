import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { AnalysisRead } from "@/api/types.gen";
import { InputsView } from "./InputsView";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

test("renders the run inputs read-back", () => {
  wrap(
    <InputsView
      data={
        {
          analysis_id: "a1",
          status: "stage_1_awaiting_approval",
          current_stage: 1,
          mode: "guided",
          stage_results: {},
          stage_state: {},
        } as AnalysisRead
      }
    />,
  );
  expect(screen.getByRole("heading", { level: 1, name: /inputs/i })).toBeInTheDocument();
  expect(screen.getByText(/guided/i)).toBeInTheDocument();
});
