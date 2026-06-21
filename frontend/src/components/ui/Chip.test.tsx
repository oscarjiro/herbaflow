import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Chip, OverflowChip } from "./Chip";

describe("Chip — removable", () => {
  it("renders the label text", () => {
    render(<Chip label="Curcumin" onRemove={vi.fn()} />);
    expect(screen.getByText("Curcumin")).toBeInTheDocument();
  });

  it("renders a remove button with accessible aria-label", () => {
    render(<Chip label="Curcumin" onRemove={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /remove curcumin/i });
    expect(btn).toBeInTheDocument();
  });

  it("fires onRemove when the × button is clicked", () => {
    const onRemove = vi.fn();
    render(<Chip label="Curcumin" onRemove={onRemove} />);
    const btn = screen.getByRole("button", { name: /remove curcumin/i });
    fireEvent.click(btn);
    expect(onRemove).toHaveBeenCalledOnce();
  });

  it("remove button is focusable (tabIndex 0)", () => {
    render(<Chip label="Turmeric" onRemove={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /remove turmeric/i });
    expect(btn.tabIndex).toBe(0);
  });

  it("accepts and forwards additional className", () => {
    const { container } = render(<Chip label="Test" onRemove={vi.fn()} className="my-custom" />);
    expect(container.firstChild).toHaveClass("my-custom");
  });
});

describe("OverflowChip", () => {
  it("renders '+N more' for N hidden items", () => {
    render(<OverflowChip count={172} />);
    expect(screen.getByText("+172 more")).toBeInTheDocument();
  });

  it("renders '+1 more' for a single hidden item", () => {
    render(<OverflowChip count={1} />);
    expect(screen.getByText("+1 more")).toBeInTheDocument();
  });

  it("accepts and forwards additional className", () => {
    const { container } = render(<OverflowChip count={5} className="extra" />);
    expect(container.firstChild).toHaveClass("extra");
  });
});
