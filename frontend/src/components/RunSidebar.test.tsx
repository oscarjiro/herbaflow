import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalysisRead } from "@/api/types.gen";
import { renderWithRouter } from "../../tests/renderWithRouter";
import { RunSidebar } from "./RunSidebar";

const DATA = {
  analysis_id: "run-1",
  status: "stage_1_awaiting_approval",
  current_stage: 1,
  stage_state: {},
  stage_results: {},
} as unknown as AnalysisRead;

afterEach(() => cleanup());

describe("RunSidebar", () => {
  it("renders the brand, the stepper rail, theme toggle, and Exit", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={() => {}} />, {
      withTheme: true,
    });
    expect(screen.getByText("Herbaflow")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /pipeline steps/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /theme:/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /exit analysis/i })).toBeInTheDocument();
  });

  it("opens the confirm dialog from Exit", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={vi.fn()} />, {
      withTheme: true,
    });
    fireEvent.click(screen.getByRole("button", { name: /exit analysis/i }));
    expect(screen.getByText(/permanently deleted/i)).toBeInTheDocument();
  });
});
