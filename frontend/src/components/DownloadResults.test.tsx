import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import type { AnalysisRead } from "../api/types.gen";
import { DownloadResults } from "./DownloadResults";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/download", () => ({
  fetchBlobDownload: vi.fn(),
}));

vi.mock("../lib/toast", () => ({
  notifySuccess: vi.fn(),
  notifyError: vi.fn(),
}));

import { fetchBlobDownload } from "../lib/download";
import { notifySuccess, notifyError } from "../lib/toast";

const mockFetchBlobDownload = vi.mocked(fetchBlobDownload);
const mockNotifySuccess = vi.mocked(notifySuccess);
const mockNotifyError = vi.mocked(notifyError);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

/** Minimal AnalysisRead fixture. Defaults to a completed run with compounds,
 * overlap (Stage 5 count > 0) and pathways (Stage 8 count > 0) — i.e. runHasCtp = true. */
function makeRun(
  overrides: Partial<{
    status: string;
    plant: string;
    stage5Count: number;
    stage8Count: number;
  }> = {},
): AnalysisRead {
  const { status = "complete", plant = "selection", stage5Count = 3, stage8Count = 5 } = overrides;
  return {
    analysis_id: "a1",
    analysis_name: null,
    disease_id: null,
    mode: "guided",
    status,
    current_stage: null,
    parameters: { input_modes: { plant } },
    stage_results: {
      "5": { count: stage5Count },
      "8": { count: stage8Count },
    },
    progress: null,
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
    stage_states: {},
  } as unknown as AnalysisRead;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DownloadResults", () => {
  it("renders nothing when not complete", () => {
    const run = makeRun({ status: "stage_8_awaiting_approval" });
    const { container } = render(
      wrap(<DownloadResults status="stage_8_awaiting_approval" analysisId="a1" run={run} />),
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders 4 download buttons when complete with compounds, overlap and pathways", () => {
    const run = makeRun();
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));
    expect(screen.getByRole("button", { name: /report/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /compound–target–pathway network \(\.zip\)/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all stages/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all results/i })).toBeInTheDocument();
  });

  it("hides the Cytoscape network bundle when the run has no pathways (runHasCtp false)", () => {
    // Stage-8 count is zero so runHasCtp returns false even though compounds exist.
    const run = makeRun({ stage8Count: 0 });
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));
    expect(
      screen.queryByRole("button", { name: /compound–target–pathway network \(\.zip\)/i }),
    ).toBeNull();
    // PPI stays reachable through the stages and all-results bundles.
    expect(screen.getByRole("button", { name: /all stages/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all results/i })).toBeInTheDocument();
  });

  it("hides the Cytoscape network bundle for target-only runs (no compounds)", () => {
    const run = makeRun({ plant: "manual_targets" });
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));
    expect(
      screen.queryByRole("button", { name: /compound–target–pathway network \(\.zip\)/i }),
    ).toBeNull();
    // PPI stays reachable through the stages and all-results bundles.
    expect(screen.getByRole("button", { name: /all stages/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all results/i })).toBeInTheDocument();
  });

  it("shows the Cytoscape network bundle when the run has compounds, overlap and pathways", () => {
    const run = makeRun({ stage5Count: 2, stage8Count: 4 });
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));
    expect(
      screen.getByRole("button", { name: /compound–target–pathway network \(\.zip\)/i }),
    ).toBeInTheDocument();
  });

  it("calls fetchBlobDownload with the correct URL on button click", async () => {
    mockFetchBlobDownload.mockResolvedValue(undefined);
    const run = makeRun();
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));

    await userEvent.click(screen.getByRole("button", { name: /report/i }));

    await waitFor(() => {
      expect(mockFetchBlobDownload).toHaveBeenCalledWith(
        expect.stringContaining("/export/report.md"),
      );
    });
  });

  it("calls notifySuccess with Downloaded <label> on success", async () => {
    mockFetchBlobDownload.mockResolvedValue(undefined);
    const run = makeRun();
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));

    await userEvent.click(screen.getByRole("button", { name: /report/i }));

    await waitFor(() => {
      expect(mockNotifySuccess).toHaveBeenCalledWith("Downloaded Report (.md)");
    });
  });

  it("calls notifyError with the problem on a failed download", async () => {
    const problem = { status: 404, title: "Not Found", detail: "Report not found." };
    mockFetchBlobDownload.mockRejectedValue(problem);
    const run = makeRun();
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));

    await userEvent.click(screen.getByRole("button", { name: /report/i }));

    await waitFor(() => {
      expect(mockNotifyError).toHaveBeenCalledWith(problem);
    });
  });

  it("disables all buttons while a download is in flight", async () => {
    // Hold the promise open to observe the pending state
    let resolveFn!: () => void;
    mockFetchBlobDownload.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveFn = resolve;
      }),
    );

    const run = makeRun();
    render(wrap(<DownloadResults status="complete" analysisId="a1" run={run} />));

    await userEvent.click(screen.getByRole("button", { name: /report/i }));

    // While pending, all buttons should be disabled
    await waitFor(() => {
      for (const btn of screen.getAllByRole("button")) {
        expect(btn).toBeDisabled();
      }
    });

    // Resolve so the mutation settles (avoids act() warning)
    resolveFn();
    await waitFor(() => {
      expect(mockNotifySuccess).toHaveBeenCalled();
    });
  });
});
