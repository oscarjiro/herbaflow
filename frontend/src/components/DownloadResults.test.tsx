import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DownloadResults } from "./DownloadResults";

describe("DownloadResults", () => {
  it("renders nothing when not complete", () => {
    const { container } = render(
      <DownloadResults status="stage_8_awaiting_approval" analysisId="a1" />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders 4 download links when complete", () => {
    render(<DownloadResults status="complete" analysisId="a1" />);
    expect(screen.getByRole("link", { name: /report/i })).toHaveAttribute(
      "href",
      expect.stringContaining("/export/report.md"),
    );
    expect(screen.getByRole("link", { name: /network/i })).toHaveAttribute(
      "href",
      expect.stringContaining("/export/network-and-docking.zip"),
    );
    expect(screen.getByRole("link", { name: /all results/i })).toHaveAttribute(
      "href",
      expect.stringContaining("/export/all-results.zip"),
    );
  });
});
