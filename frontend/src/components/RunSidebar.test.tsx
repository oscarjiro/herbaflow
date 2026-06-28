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
  it("renders the brand, the stepper rail, theme toggle, and exit button", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={() => {}} />, {
      withTheme: true,
    });
    const brandLink = screen.getByRole("link", { name: /herbaflow home/i });
    expect(brandLink).toBeInTheDocument();
    expect(brandLink.querySelector(".hf-logo")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /pipeline steps/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /theme:/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /exit run/i })).toBeInTheDocument();
  });

  it("renders the run-identity card with Untitled analysis fallback", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={() => {}} />, {
      withTheme: true,
    });
    expect(screen.getByText("Untitled analysis")).toBeInTheDocument();
  });

  it("renders the 'Active run' label in the run-card", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={() => {}} />, {
      withTheme: true,
    });
    expect(screen.getByText("Active run")).toBeInTheDocument();
  });

  it("renders the exit-run trigger as a glass danger button", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={() => {}} />, {
      withTheme: true,
    });
    const exit = screen.getByRole("button", { name: /exit run/i });
    // Every button is glass (UX-9); the trigger carries the layered .hf-glass recipe...
    expect(exit.className).toContain("hf-glass");
    // ...and keeps destructive red semantics through the colored label.
    expect(exit.querySelector(".text-hf-danger")).not.toBeNull();
  });

  it("opens the confirm dialog from Exit run", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={vi.fn()} />, {
      withTheme: true,
    });
    fireEvent.click(screen.getByRole("button", { name: /exit run/i }));
    expect(screen.getByText(/permanently deleted/i)).toBeInTheDocument();
  });

  it("marks the active stage from the current route path", () => {
    renderWithRouter(<RunSidebar data={DATA} analysisId="run-1" onExit={() => {}} />, {
      withTheme: true,
      initialEntries: ["/analysis/run-1/targets"],
    });
    const active = document.querySelector('[aria-current="step"]');
    expect(active).not.toBeNull();
    expect(active).toHaveTextContent(/targets/i);
  });
});
