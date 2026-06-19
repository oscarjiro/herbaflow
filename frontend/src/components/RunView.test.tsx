import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { RunView } from "./RunView";
import * as useAnalysisStatusModule from "../hooks/useAnalysisStatus";
import type { AnalysisRead } from "../api/types.gen";

// Mock advanceAnalysis so mutations don't fire real requests
vi.mock("../api/sdk.gen", () => ({
  advanceAnalysis: vi.fn().mockResolvedValue({ data: {} }),
  resetFrom: vi.fn().mockResolvedValue({ data: {} }),
}));

function makeRun(overrides: Partial<AnalysisRead>): AnalysisRead {
  return {
    analysis_id: "run-1",
    analysis_name: null,
    disease_id: "d1",
    mode: "auto",
    status: "complete",
    current_stage: 8,
    stage_results: {},
    stage_state: {},
    parameters: {},
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
    plants: [],
    diseases: [],
    compounds: [],
    ...overrides,
  } as unknown as AnalysisRead;
}

function mockStatus(
  data: AnalysisRead | undefined,
  overrides: { isError?: boolean; error?: unknown } = {},
) {
  vi.spyOn(useAnalysisStatusModule, "useAnalysisStatus").mockReturnValue({
    data,
    isLoading: data == null && !overrides.isError,
    isError: overrides.isError ?? false,
    error: overrides.error ?? null,
  } as ReturnType<typeof useAnalysisStatusModule.useAnalysisStatus>);
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("RunView — running skeleton", () => {
  it("shows the running skeleton for the active stage when no result has landed", () => {
    mockStatus(
      makeRun({
        status: "stage_3_running",
        current_stage: 3,
        // Only stage_results["1"] present; "3" absent — result not yet landed.
        // Stages 2+ are absent to avoid crashing Stage2View with malformed fixture data.
        stage_results: {},
      }),
    );
    wrap(<RunView analysisId="run-1" />);
    // The skeleton section is accessible by its aria-label
    const skeleton = screen.getByRole("region", { name: "Step 3 running" });
    expect(skeleton).toBeInTheDocument();
    // The heading within the skeleton contains the stage label
    expect(skeleton).toHaveTextContent("Compound targets");
    expect(skeleton).toHaveTextContent("running…");
  });

  it("does NOT show a running skeleton when the status is settled (awaiting_approval)", () => {
    mockStatus(
      makeRun({
        status: "stage_3_awaiting_approval",
        current_stage: 3,
        stage_results: {},
      }),
    );
    wrap(<RunView analysisId="run-1" />);
    expect(screen.queryByRole("region", { name: /running/i })).toBeNull();
  });

  it("does NOT show a running skeleton when the result has already landed", () => {
    // Use stage 5 (overlap) — its result shape is a simple flat object with arrays,
    // so Stage5View won't crash on a minimal fixture. The test proves the skeleton
    // disappears once stage_results[N] is present, regardless of which stage it is.
    mockStatus(
      makeRun({
        status: "stage_5_running",
        current_stage: 5,
        stage_results: {
          "5": {
            state: "computed",
            overlap: [],
            count: 0,
            compound_target_count: 0,
            disease_target_count: 0,
            unmapped_count: 0,
            flags: [],
          } as never,
        },
      }),
    );
    wrap(<RunView analysisId="run-1" />);
    expect(screen.queryByRole("region", { name: "Step 5 running" })).toBeNull();
  });

  it("shows a loading skeleton when data is not yet available", () => {
    mockStatus(undefined);
    wrap(<RunView analysisId="run-1" />);
    // Should render initial loading skeletons, not stage content
    expect(screen.queryByText(/running…/)).toBeNull();
  });
});

describe("RunView — poll-error banner", () => {
  it("renders an error banner when the poll errors with no data yet", () => {
    mockStatus(undefined, {
      isError: true,
      error: { detail: "Service temporarily unavailable." },
    });
    wrap(<RunView analysisId="run-1" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/could not load analysis status/i)).toBeInTheDocument();
    expect(screen.getByText(/service temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/retrying/i)).toBeInTheDocument();
  });

  it("does not render the error banner when data is already available despite an error", () => {
    mockStatus(makeRun({ status: "complete", current_stage: 8 }), {
      isError: true,
      error: { detail: "Transient blip." },
    });
    wrap(<RunView analysisId="run-1" />);
    // Run header should still render, no alert banner
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText(/run-1/)).toBeInTheDocument();
  });
});
