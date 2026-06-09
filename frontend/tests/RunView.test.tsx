import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, test } from "vitest";
import { RunView } from "../src/components/RunView";
import "../src/lib/api";

function wrap(analysisId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RunView analysisId={analysisId} />
    </QueryClientProvider>,
  );
}

test("renders the stage 1 compound list", async () => {
  wrap("r1");
  expect(await screen.findByText("Alpha")).toBeInTheDocument();
  expect(await screen.findByText(/status: complete/i)).toBeInTheDocument();
});

describe("RunView with Stage 2 data", () => {
  it("renders Stage 2 view when stage_results['2'] is present", async () => {
    wrap("r2");
    // Stage 2 section header appears once data loads
    expect(await screen.findByRole("heading", { name: /step 2/i })).toBeInTheDocument();
    // Compound names appear in the table (may appear multiple times across stage1 list + table)
    const curcuminEls = await screen.findAllByText("Curcumin");
    expect(curcuminEls.length).toBeGreaterThan(0);
  });

  it("shows ApprovalBar at stage_2_awaiting_approval", async () => {
    wrap("r2");
    // Wait for data to load — heading is a reliable marker
    await screen.findByRole("heading", { name: /step 2/i });
    // Approve button should already be in DOM once heading is present
    const approveBtns = screen.getAllByRole("button", { name: /approve/i });
    expect(approveBtns.length).toBeGreaterThan(0);
  });

  it("does NOT show approve button for r1 which is complete", async () => {
    wrap("r1");
    await screen.findByText("Alpha");
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });
});
