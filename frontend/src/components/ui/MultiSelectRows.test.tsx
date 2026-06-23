/**
 * MultiSelectRows: selectable list rows with hover fill and animated check.
 *
 * jsdom cannot evaluate CSS variables or transitions, so we assert:
 * - rows render with their labels
 * - optional meta slot renders when provided
 * - clicking a row fires onChange with the updated selection set
 * - selected rows carry aria-selected="true", unselected carry aria-selected="false"
 * - selected rows carry a data-selected attribute (drives check visibility)
 * - the check element is present for every row (hidden via CSS when unselected)
 * - the container carries the correct token-based class for hover fill
 * - keyboard Space/Enter toggles a row
 * - focus ring class is present
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MultiSelectRows } from "./MultiSelectRows";

const items = [
  { id: "a", label: "Curcumin" },
  { id: "b", label: "Demethoxycurcumin", meta: "2 targets" },
  { id: "c", label: "Bisdemethoxycurcumin", meta: "0 targets" },
];

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("MultiSelectRows — rendering", () => {
  it("renders all row labels", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    expect(screen.getByText("Curcumin")).toBeInTheDocument();
    expect(screen.getByText("Demethoxycurcumin")).toBeInTheDocument();
    expect(screen.getByText("Bisdemethoxycurcumin")).toBeInTheDocument();
  });

  it("renders meta text when provided", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    expect(screen.getByText("2 targets")).toBeInTheDocument();
    expect(screen.getByText("0 targets")).toBeInTheDocument();
  });

  it("does not render meta for rows without meta", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    // Only 2 meta slots visible (items b and c)
    const metas = document.querySelectorAll("[data-slot='row-meta']");
    expect(metas).toHaveLength(2);
  });

  it("renders a check element for every row", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    const checks = document.querySelectorAll("[data-slot='row-check']");
    expect(checks).toHaveLength(3);
  });

  it("renders three rows total", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    const rows = screen.getAllByRole("option");
    expect(rows).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// aria-selected reflects controlled selected set
// ---------------------------------------------------------------------------

describe("MultiSelectRows — aria-selected", () => {
  it("unselected rows carry aria-selected=false", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    const rows = screen.getAllByRole("option");
    rows.forEach((row) => {
      expect(row).toHaveAttribute("aria-selected", "false");
    });
  });

  it("selected rows carry aria-selected=true", () => {
    render(<MultiSelectRows items={items} selected={new Set(["a", "c"])} onChange={() => {}} />);
    const rowA = screen.getByRole("option", { name: "Curcumin" });
    const rowB = screen.getByRole("option", { name: "Demethoxycurcumin" });
    const rowC = screen.getByRole("option", { name: "Bisdemethoxycurcumin" });
    expect(rowA).toHaveAttribute("aria-selected", "true");
    expect(rowB).toHaveAttribute("aria-selected", "false");
    expect(rowC).toHaveAttribute("aria-selected", "true");
  });
});

// ---------------------------------------------------------------------------
// data-selected drives check visibility
// ---------------------------------------------------------------------------

describe("MultiSelectRows — data-selected", () => {
  it("selected rows carry data-selected=true", () => {
    render(<MultiSelectRows items={items} selected={new Set(["b"])} onChange={() => {}} />);
    const rowB = screen.getByRole("option", { name: "Demethoxycurcumin" });
    expect(rowB).toHaveAttribute("data-selected", "true");
  });

  it("unselected rows carry data-selected=false", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    const rows = screen.getAllByRole("option");
    rows.forEach((row) => {
      expect(row).toHaveAttribute("data-selected", "false");
    });
  });
});

// ---------------------------------------------------------------------------
// onChange fires with updated selection
// ---------------------------------------------------------------------------

describe("MultiSelectRows — onChange", () => {
  it("clicking an unselected row calls onChange with that id added", () => {
    const onChange = vi.fn();
    render(<MultiSelectRows items={items} selected={new Set()} onChange={onChange} />);
    fireEvent.click(screen.getByRole("option", { name: "Curcumin" }));
    expect(onChange).toHaveBeenCalledOnce();
    const next: Set<string> = onChange.mock.calls[0]![0] as Set<string>;
    expect(next.has("a")).toBe(true);
  });

  it("clicking a selected row calls onChange with that id removed", () => {
    const onChange = vi.fn();
    render(<MultiSelectRows items={items} selected={new Set(["a"])} onChange={onChange} />);
    fireEvent.click(screen.getByRole("option", { name: "Curcumin" }));
    expect(onChange).toHaveBeenCalledOnce();
    const next: Set<string> = onChange.mock.calls[0]![0] as Set<string>;
    expect(next.has("a")).toBe(false);
  });

  it("toggling preserves other selected ids", () => {
    const onChange = vi.fn();
    render(<MultiSelectRows items={items} selected={new Set(["a", "c"])} onChange={onChange} />);
    fireEvent.click(screen.getByRole("option", { name: "Demethoxycurcumin" }));
    const next: Set<string> = onChange.mock.calls[0]![0] as Set<string>;
    expect(next.has("a")).toBe(true);
    expect(next.has("b")).toBe(true);
    expect(next.has("c")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Keyboard toggle (Space / Enter)
// ---------------------------------------------------------------------------

describe("MultiSelectRows — keyboard toggle", () => {
  it("Space key calls onChange", () => {
    const onChange = vi.fn();
    render(<MultiSelectRows items={items} selected={new Set()} onChange={onChange} />);
    const row = screen.getByRole("option", { name: "Curcumin" });
    row.focus();
    fireEvent.keyDown(row, { key: " ", code: "Space" });
    expect(onChange).toHaveBeenCalledOnce();
  });

  it("Enter key calls onChange", () => {
    const onChange = vi.fn();
    render(<MultiSelectRows items={items} selected={new Set()} onChange={onChange} />);
    const row = screen.getByRole("option", { name: "Curcumin" });
    row.focus();
    fireEvent.keyDown(row, { key: "Enter", code: "Enter" });
    expect(onChange).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// CSS class tokens (hover fill, focus ring)
// ---------------------------------------------------------------------------

describe("MultiSelectRows — CSS class tokens", () => {
  it("each row carries the hover fill token class", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    const rows = screen.getAllByRole("option");
    rows.forEach((row) => {
      expect(row.className).toMatch(/hover:bg-hf-surface-2/);
    });
  });

  it("each row carries a focus-visible ring class", () => {
    render(<MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />);
    const rows = screen.getAllByRole("option");
    rows.forEach((row) => {
      expect(row.className).toMatch(/focus-visible:/);
    });
  });

  it("container carries border and surface class", () => {
    const { container } = render(
      <MultiSelectRows items={items} selected={new Set()} onChange={() => {}} />,
    );
    const wrapper = container.querySelector("[data-slot='multi-select-rows']")!;
    expect(wrapper.className).toMatch(/border/);
    expect(wrapper.className).toMatch(/bg-hf-surface/);
  });
});
