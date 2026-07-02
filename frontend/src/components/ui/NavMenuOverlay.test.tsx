import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithRouter } from "../../../tests/renderWithRouter";
import { NavMenuOverlay } from "./NavMenuOverlay";

afterEach(() => cleanup());

describe("NavMenuOverlay", () => {
  it("renders logo, Analysis, About, and an icon-only theme toggle", () => {
    renderWithRouter(<NavMenuOverlay open onClose={vi.fn()} />, {
      initialEntries: ["/"],
      withTheme: true,
    });
    const dialog = screen.getByRole("dialog", { name: /navigation/i });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Herbaflow home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Analysis" })).toHaveAttribute("href", "/analysis");
    expect(screen.getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
    // Theme control is present but carries NO visible "Theme" text label.
    expect(screen.getByRole("button", { name: /theme: system/i })).toBeInTheDocument();
    expect(screen.queryByText(/^theme$/i)).not.toBeInTheDocument();
  });

  it("closes when a nav link is clicked", () => {
    const onClose = vi.fn();
    renderWithRouter(<NavMenuOverlay open onClose={onClose} />, {
      initialEntries: ["/"],
      withTheme: true,
    });
    fireEvent.click(screen.getByRole("link", { name: "About" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("does not close when the theme toggle is clicked", () => {
    const onClose = vi.fn();
    renderWithRouter(<NavMenuOverlay open onClose={onClose} />, {
      initialEntries: ["/"],
      withTheme: true,
    });
    fireEvent.click(screen.getByRole("button", { name: /theme: system/i }));
    expect(onClose).not.toHaveBeenCalled();
  });
});
