import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BoolMark } from "./BoolMark";

describe("BoolMark", () => {
  it("shows the yes mark with aria-label Yes for true", () => {
    render(<BoolMark value={true} />);
    const el = screen.getByLabelText("Yes");
    expect(el).toBeInTheDocument();
    expect(el.textContent).toBe("✓");
  });

  it("applies success color class for true", () => {
    render(<BoolMark value={true} />);
    const el = screen.getByLabelText("Yes");
    expect(el.className).toContain("text-hf-success");
  });

  it("shows the no mark with aria-label No for false", () => {
    render(<BoolMark value={false} />);
    const el = screen.getByLabelText("No");
    expect(el).toBeInTheDocument();
    expect(el.textContent).toBe("✗");
  });

  it("applies danger color class for false", () => {
    render(<BoolMark value={false} />);
    const el = screen.getByLabelText("No");
    expect(el.className).toContain("text-hf-danger");
  });

  it("shows the not-applicable mark with aria-label 'Not applicable' for null", () => {
    render(<BoolMark value={null} />);
    const el = screen.getByLabelText("Not applicable");
    expect(el).toBeInTheDocument();
    // en dash character
    expect(el.textContent).toBe("–");
  });

  it("shows the not-applicable mark for undefined", () => {
    render(<BoolMark value={undefined} />);
    const el = screen.getByLabelText("Not applicable");
    expect(el).toBeInTheDocument();
  });

  it("applies muted color class for null", () => {
    render(<BoolMark value={null} />);
    const el = screen.getByLabelText("Not applicable");
    expect(el.className).toContain("text-hf-fg-4");
  });
});
