import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StaleNotice } from "./StaleNotice";
import * as sdk from "../../api/sdk.gen";
import * as toastLib from "../../lib/toast";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("StaleNotice", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders the cleaned stale-results notice copy", () => {
    wrap(<StaleNotice analysisId="a1" fromStage={1} />);
    expect(
      screen.getByText("These results are out of date. An earlier step changed."),
    ).toBeInTheDocument();
  });

  it("re-runs from the given stage when clicked", async () => {
    const spy = vi.spyOn(sdk, "resetFrom").mockResolvedValue({ data: {} } as never);
    wrap(<StaleNotice analysisId="a1" fromStage={1} />);
    await userEvent.click(screen.getByRole("button", { name: /re-run from step 1/i }));
    expect(spy).toHaveBeenCalledWith({
      path: { analysis_id: "a1", stage: 1 },
      body: {},
      throwOnError: true,
    });
  });

  it("fires notifyInfo with the correct step number on rerun success", async () => {
    vi.spyOn(sdk, "resetFrom").mockResolvedValue({ data: {} } as never);
    const notifyInfoSpy = vi.spyOn(toastLib, "notifyInfo").mockImplementation(() => {});

    wrap(<StaleNotice analysisId="a1" fromStage={3} />);
    await userEvent.click(screen.getByRole("button", { name: /re-run from step 3/i }));

    await waitFor(() => expect(notifyInfoSpy).toHaveBeenCalledWith("Re-running from step 3"));
  });

  it("fires notifyError when the rerun mutation fails", async () => {
    vi.spyOn(sdk, "resetFrom").mockRejectedValue({ detail: "Server error." });
    const notifyErrorSpy = vi.spyOn(toastLib, "notifyError").mockImplementation(() => {});

    wrap(<StaleNotice analysisId="a1" fromStage={2} />);
    await userEvent.click(screen.getByRole("button", { name: /re-run from step 2/i }));

    await waitFor(() => expect(notifyErrorSpy).toHaveBeenCalledTimes(1));
  });
});
