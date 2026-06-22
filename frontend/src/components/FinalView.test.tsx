import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AnalysisRead } from "@/api/types.gen";
import { FinalView } from "./FinalView";

vi.mock("react-cytoscapejs", () => import("@/test-utils/cytoscapeMock"));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }));

function renderFinal(data: AnalysisRead) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <FinalView analysisId="a1" data={data} />
    </QueryClientProvider>,
  );
}

test("renders the final summary grid and the export surface when complete", () => {
  renderFinal({
    analysis_id: "a1",
    status: "complete",
    current_stage: 8,
    stage_results: { "7": { count: 9 }, "8": { count: 24 } },
    stage_state: {},
  } as unknown as AnalysisRead);
  expect(screen.getByRole("heading", { level: 1, name: /results|final/i })).toBeInTheDocument();
  expect(screen.getByText(/download/i)).toBeInTheDocument();
});
