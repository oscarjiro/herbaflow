import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithRouter } from "../../tests/renderWithRouter";
import { ServiceUnavailable } from "./ServiceUnavailable";

describe("ServiceUnavailable", () => {
  it("fires onRetry when Retry is clicked", () => {
    const onRetry = vi.fn();
    renderWithRouter(<ServiceUnavailable onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("links back to landing", () => {
    renderWithRouter(<ServiceUnavailable onRetry={() => {}} />);
    const link = screen.getByRole("link", { name: /back to landing/i });
    expect(link.getAttribute("href")).toBe("/");
  });
});
