import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
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
    const { container } = render(
      wrap(<DownloadResults status="stage_8_awaiting_approval" analysisId="a1" />),
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders 4 download buttons when complete (with compounds)", () => {
    render(wrap(<DownloadResults status="complete" analysisId="a1" />));
    expect(screen.getByRole("button", { name: /report/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /network/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all stages/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all results/i })).toBeInTheDocument();
  });

  it("hides the network-and-docking bundle for target-only runs (it would 404)", () => {
    render(wrap(<DownloadResults status="complete" analysisId="a1" hasCompounds={false} />));
    expect(screen.queryByRole("button", { name: /network/i })).toBeNull();
    // PPI stays reachable through the stages and all-results bundles.
    expect(screen.getByRole("button", { name: /all stages/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all results/i })).toBeInTheDocument();
  });

  it("calls fetchBlobDownload with the correct URL on button click", async () => {
    mockFetchBlobDownload.mockResolvedValue(undefined);
    render(wrap(<DownloadResults status="complete" analysisId="a1" />));

    await userEvent.click(screen.getByRole("button", { name: /report/i }));

    await waitFor(() => {
      expect(mockFetchBlobDownload).toHaveBeenCalledWith(
        expect.stringContaining("/export/report.md"),
      );
    });
  });

  it("calls notifySuccess with Downloaded <label> on success", async () => {
    mockFetchBlobDownload.mockResolvedValue(undefined);
    render(wrap(<DownloadResults status="complete" analysisId="a1" />));

    await userEvent.click(screen.getByRole("button", { name: /report/i }));

    await waitFor(() => {
      expect(mockNotifySuccess).toHaveBeenCalledWith("Downloaded Report (.md)");
    });
  });

  it("calls notifyError with the problem on a failed download", async () => {
    const problem = { status: 404, title: "Not Found", detail: "Report not found." };
    mockFetchBlobDownload.mockRejectedValue(problem);
    render(wrap(<DownloadResults status="complete" analysisId="a1" />));

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

    render(wrap(<DownloadResults status="complete" analysisId="a1" />));

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
