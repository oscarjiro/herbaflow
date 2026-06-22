import { screen } from "@testing-library/react";
import * as useAnalysisStatusModule from "@/hooks/useAnalysisStatus";
import type { AnalysisRead } from "@/api/types.gen";
import { renderWithRouter } from "../../tests/renderWithRouter";
import { RunStageContent } from "./RunStageContent";

vi.mock("react-cytoscapejs", () => import("@/test-utils/cytoscapeMock"));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }));
vi.mock("@/api/sdk.gen", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  advanceAnalysis: vi.fn().mockResolvedValue({ data: {} }),
}));

function mountSlug(data: AnalysisRead, slug: string) {
  vi.spyOn(useAnalysisStatusModule, "useAnalysisStatus").mockReturnValue({
    data,
    isError: false,
    error: null,
  } as ReturnType<typeof useAnalysisStatusModule.useAnalysisStatus>);
  return renderWithRouter(<RunStageContent analysisId="a1" slug={slug as never} />, {
    withTheme: true,
  });
}

test("renders the StageView for a reached pipeline slug", () => {
  // Stage 5 (overlap → "Shared targets") has a flat result shape that renders
  // from a minimal fixture, mirroring the proven RunView "result landed" case.
  mountSlug(
    {
      analysis_id: "a1",
      status: "stage_5_awaiting_approval",
      current_stage: 5,
      stage_results: {
        "5": {
          state: "computed",
          overlap: [],
          count: 2,
          compound_target_count: 0,
          disease_target_count: 0,
          unmapped_count: 0,
          flags: [],
        },
      },
      stage_state: {},
    } as unknown as AnalysisRead,
    "overlap",
  );
  expect(screen.getByRole("heading", { level: 1, name: /shared targets/i })).toBeInTheDocument();
});
