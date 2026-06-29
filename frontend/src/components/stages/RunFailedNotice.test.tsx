import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RunFailedNotice } from "./RunFailedNotice";
import * as sdk from "../../api/sdk.gen";
import * as toastLib from "../../lib/toast";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("RunFailedNotice", () => {
  afterEach(() => vi.restoreAllMocks());

  it("names the failed step and shows the backend's reason", () => {
    wrap(
      <RunFailedNotice
        analysisId="a1"
        failedStage={6}
        message="The server restarted while this analysis was running. Please run it again."
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/step 6 failed/i)).toBeInTheDocument();
    expect(screen.getByText(/server restarted/i)).toBeInTheDocument();
  });

  it("re-runs from the failed stage when clicked", async () => {
    const spy = vi.spyOn(sdk, "resetFrom").mockResolvedValue({ data: {} } as never);
    wrap(<RunFailedNotice analysisId="a1" failedStage={6} message="boom" />);
    await userEvent.click(screen.getByRole("button", { name: /re-run from step 6/i }));
    expect(spy).toHaveBeenCalledWith({
      path: { analysis_id: "a1", stage: 6 },
      body: {},
      throwOnError: true,
    });
  });

  it("fires notifyInfo with the step number on rerun success", async () => {
    vi.spyOn(sdk, "resetFrom").mockResolvedValue({ data: {} } as never);
    const notifyInfoSpy = vi.spyOn(toastLib, "notifyInfo").mockImplementation(() => {});
    wrap(<RunFailedNotice analysisId="a1" failedStage={3} message="boom" />);
    await userEvent.click(screen.getByRole("button", { name: /re-run from step 3/i }));
    await waitFor(() => expect(notifyInfoSpy).toHaveBeenCalledWith("Re-running from step 3"));
  });

  it("surfaces an error (no false success toast) when reset-from is rejected", async () => {
    vi.spyOn(sdk, "resetFrom").mockRejectedValue({ detail: "Stage 6 has not been computed yet." });
    const notifyErrorSpy = vi.spyOn(toastLib, "notifyError").mockImplementation(() => {});
    const notifyInfoSpy = vi.spyOn(toastLib, "notifyInfo").mockImplementation(() => {});
    wrap(<RunFailedNotice analysisId="a1" failedStage={6} message="boom" />);
    await userEvent.click(screen.getByRole("button", { name: /re-run from step 6/i }));
    await waitFor(() => expect(notifyErrorSpy).toHaveBeenCalledTimes(1));
    expect(notifyInfoSpy).not.toHaveBeenCalled();
  });

  it("renders without a message (no reason line)", () => {
    wrap(<RunFailedNotice analysisId="a1" failedStage={2} />);
    expect(screen.getByText(/step 2 failed/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /re-run from step 2/i })).toBeInTheDocument();
  });
});
