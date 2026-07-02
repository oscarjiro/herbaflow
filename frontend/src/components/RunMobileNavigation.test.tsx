import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalysisRead } from "@/api/types.gen";
import { renderWithRouter } from "../../tests/renderWithRouter";
import { RunMobileNavigation } from "./RunMobileNavigation";

const DATA = {
  analysis_id: "run-1",
  status: "stage_1_awaiting_approval",
  current_stage: 1,
  stage_state: {},
  stage_results: { "1": { count: 2 } },
} as unknown as AnalysisRead;

function renderNav() {
  return renderWithRouter(
    <RunMobileNavigation
      data={DATA}
      analysisId="run-1"
      onExit={vi.fn()}
      pathname="/analysis/run-1/compounds"
    />,
    { withTheme: true, initialEntries: ["/analysis/run-1/compounds"] },
  );
}

afterEach(() => cleanup());

describe("RunMobileNavigation", () => {
  it("shows the current step and status in the compact bar", () => {
    renderNav();
    expect(screen.getByText("Step 1")).toBeInTheDocument();
    expect(screen.getByText("Awaiting approval")).toBeInTheDocument();
  });

  it("opens the full run drawer from the burger", () => {
    renderNav();
    fireEvent.click(screen.getByRole("button", { name: /open run navigation/i }));
    const dialog = screen.getByRole("dialog", { name: /run navigation/i });
    expect(within(dialog).getByRole("navigation", { name: /pipeline steps/i })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /exit run/i })).toBeInTheDocument();
  });

  it("closes the drawer when a drawer step is selected", () => {
    renderNav();
    fireEvent.click(screen.getByRole("button", { name: /open run navigation/i }));
    const dialog = screen.getByRole("dialog", { name: /run navigation/i });
    fireEvent.click(within(dialog).getByRole("link", { name: /compounds/i }));
    expect(screen.queryByRole("dialog", { name: /run navigation/i })).not.toBeInTheDocument();
  });

  it("keeps Exit run inside the drawer only", () => {
    renderNav();
    expect(screen.queryByRole("button", { name: /exit run/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /open run navigation/i }));
    expect(screen.getByRole("button", { name: /exit run/i })).toBeInTheDocument();
  });
});
