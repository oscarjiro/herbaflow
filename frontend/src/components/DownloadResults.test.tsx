import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DownloadResults } from "./DownloadResults";

describe("DownloadResults", () => {
  it("renders nothing until the run is complete", () => {
    render(<DownloadResults status="stage_8_awaiting_approval" analysisId="a1" />);
    expect(screen.queryByRole("link", { name: /download results/i })).toBeNull();
  });

  it("shows a Download results link pointing at the export URL when complete", () => {
    render(<DownloadResults status="complete" analysisId="a1" />);
    const link = screen.getByRole("link", { name: /download results/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("/analyses/a1/export"));
  });
});
