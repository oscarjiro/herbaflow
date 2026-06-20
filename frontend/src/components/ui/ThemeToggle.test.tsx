import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { ThemeProvider } from "@/lib/theme";
import { ThemeToggle } from "./ThemeToggle";

beforeEach(() => localStorage.clear());

describe("ThemeToggle", () => {
  it("cycles system → light → dark → system and persists", () => {
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    const btn = screen.getByRole("button", { name: /theme:/i });
    expect(btn).toHaveAttribute("aria-label", expect.stringContaining("system"));
    fireEvent.click(btn);
    expect(localStorage.getItem("hf-theme")).toBe("light");
    fireEvent.click(btn);
    expect(localStorage.getItem("hf-theme")).toBe("dark");
    fireEvent.click(btn);
    expect(localStorage.getItem("hf-theme")).toBe("system");
  });
});
