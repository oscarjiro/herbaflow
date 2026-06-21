import React from "react";
import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { RunView } from "./RunView";
import { renderWithRouter } from "../../tests/renderWithRouter";
import { clearActiveRunId, getActiveRunId, setActiveRunId } from "../lib/activeRun";
import * as useAnalysisStatusModule from "../hooks/useAnalysisStatus";
import type { AnalysisRead } from "../api/types.gen";

// Mock react-cytoscapejs so the graph never really renders in jsdom.
// The stub cy object must have chainable off/on so NetworkGraph's nodeTooltip
// wiring (cy.off(...).on(...)) does not throw.
vi.mock("react-cytoscapejs", () => ({
  default: ({ cy, elements }: { cy?: (c: unknown) => void; elements?: unknown[] }) => {
    const stubCy: Record<string, unknown> = {
      png: () => "data:image/png;base64,AAAA",
    };
    stubCy.off = () => stubCy;
    stubCy.on = () => stubCy;
    cy?.(stubCy);
    return React.createElement("div", {
      "data-testid": "cytoscape",
      "data-count": String(elements?.length ?? 0),
    });
  },
}));

// Mock sonner so the self-heal toast can be asserted without a mounted Toaster.
vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
  Toaster: () => null,
}));

// Mock sdk.gen so mutations don't fire real requests.
// getCtpGraph must also be present so that getCtpGraphOptions (which imports it)
// can function; it is NOT mocked to a stub — the real HTTP call goes through MSW.
vi.mock("../api/sdk.gen", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/sdk.gen")>();
  return {
    ...original,
    advanceAnalysis: vi.fn().mockResolvedValue({ data: {} }),
    resetFrom: vi.fn().mockResolvedValue({ data: {} }),
  };
});

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
  return renderWithRouter(ui, { withTheme: true });
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

describe("RunView — CTP network graph", () => {
  it("renders the NetworkGraph frame title and Download PNG button for a complete run with compounds", async () => {
    // A complete run that has compounds (default input_modes = selection → has compounds).
    mockStatus(
      makeRun({
        status: "complete",
        current_stage: 8,
        // No input_modes override → runHasCompounds returns true.
      }),
    );
    wrap(<RunView analysisId="run-1" />);
    // The MSW handler returns 3 nodes so the graph should appear.
    await waitFor(() => {
      expect(screen.getByText("Compound, target and pathway network")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
  });

  it("does not render the old server-rendered ctp-network.png img", async () => {
    mockStatus(makeRun({ status: "complete", current_stage: 8 }));
    wrap(<RunView analysisId="run-1" />);
    // Wait for the graph to settle, then assert the old img is absent.
    await waitFor(() => {
      expect(screen.getByText("Compound, target and pathway network")).toBeInTheDocument();
    });
    const imgs = screen.queryAllByRole("img");
    expect(imgs.some((el) => el.getAttribute("src")?.includes("ctp-network.png"))).toBe(false);
  });

  it("does NOT render the CTP graph for a compound-free (manual_targets) run", () => {
    // manual_targets plant mode → runHasCompounds = false → query never fires.
    mockStatus(
      makeRun({
        status: "complete",
        current_stage: 8,
        parameters: {
          input_modes: { plant: "manual_targets", disease: "selection" },
        },
      }),
    );
    wrap(<RunView analysisId="run-1" />);
    // The graph title must never appear.
    expect(screen.queryByText("Compound, target and pathway network")).toBeNull();
  });
});

describe("RunView — self-heal on a deleted or expired run (404)", () => {
  beforeEach(() => {
    vi.mocked(toast.error).mockClear();
    clearActiveRunId();
  });
  afterEach(() => {
    clearActiveRunId();
  });

  it("clears the cached run, toasts, and calls onReset when the run 404s", async () => {
    // The poll surfaces a thrown RFC 9457 problem body that carries status: 404.
    mockStatus(undefined, {
      isError: true,
      error: { type: "about:blank", title: "Not Found", status: 404, detail: "not found" },
    });
    setActiveRunId("gone-1");
    const onReset = vi.fn();

    wrap(<RunView analysisId="gone-1" onReset={onReset} />);

    await waitFor(() => expect(onReset).toHaveBeenCalled());
    expect(getActiveRunId()).toBeNull();
    expect(toast.error).toHaveBeenCalledTimes(1);
  });

  it("does NOT self-heal on a non-404 poll error", async () => {
    mockStatus(undefined, {
      isError: true,
      error: { status: 503, detail: "Service temporarily unavailable." },
    });
    setActiveRunId("run-1");
    const onReset = vi.fn();

    wrap(<RunView analysisId="run-1" onReset={onReset} />);

    // Give effects a tick to run; nothing should fire for a transient error.
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(onReset).not.toHaveBeenCalled();
    expect(getActiveRunId()).toBe("run-1");
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("caches the active run id when a valid run loads via deep link", () => {
    clearActiveRunId();
    mockStatus(makeRun({ analysis_id: "deep-1", status: "complete", current_stage: 8 }));

    wrap(<RunView analysisId="deep-1" />);

    expect(getActiveRunId()).toBe("deep-1");
  });
});
