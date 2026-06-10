import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { StaleNotice } from "./StaleNotice";
import * as sdk from "../../api/sdk.gen";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("StaleNotice", () => {
  it("re-runs from the given stage when clicked", async () => {
    const spy = vi.spyOn(sdk, "resetFrom").mockResolvedValue({ data: {} } as never);
    wrap(<StaleNotice analysisId="a1" fromStage={1} />);
    await userEvent.click(screen.getByRole("button", { name: /re-run from step 1/i }));
    expect(spy).toHaveBeenCalledWith({
      path: { analysis_id: "a1", stage: 1 },
      body: {},
    });
  });
});
