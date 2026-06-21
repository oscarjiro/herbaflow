/**
 * Task 6 — Textarea: animated ink-border focus, invalid state, char cap.
 */
import { render, fireEvent } from "@testing-library/react";
import { Textarea } from "./textarea";

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
});

describe("Textarea — base rendering", () => {
  it("renders a <textarea> element", () => {
    const { container } = render(<Textarea />);
    expect(container.querySelector("textarea")).toBeTruthy();
  });

  it("carries data-slot='textarea'", () => {
    const { container } = render(<Textarea />);
    expect(container.querySelector("[data-slot='textarea']")).toBeTruthy();
  });

  it("applies surface-fill class (bg-hf-surface)", () => {
    const { container } = render(<Textarea />);
    expect(container.querySelector("textarea")!.className).toMatch(/bg-hf-surface/);
  });

  it("applies soft border class (border-hf-border-strong)", () => {
    const { container } = render(<Textarea />);
    expect(container.querySelector("textarea")!.className).toMatch(/border-hf-border-strong/);
  });

  it("applies radius-sm class (rounded-sm)", () => {
    const { container } = render(<Textarea />);
    expect(container.querySelector("textarea")!.className).toMatch(/rounded-sm/);
  });

  it("applies placeholder colour token class", () => {
    const { container } = render(<Textarea placeholder="test" />);
    expect(container.querySelector("textarea")!.className).toMatch(/placeholder:text-hf-fg-[34]/);
  });

  it("passes arbitrary className through", () => {
    const { container } = render(<Textarea className="my-custom" />);
    expect(container.querySelector("textarea")!.className).toMatch(/my-custom/);
  });
});

describe("Textarea — focus behaviour (class-level)", () => {
  it("does NOT apply legacy ring classes", () => {
    const { container } = render(<Textarea />);
    const el = container.querySelector("textarea")!;
    expect(el.className).not.toMatch(/focus-visible:ring-\[3px\]/);
    expect(el.className).not.toMatch(/focus-visible:ring-ring/);
  });

  it("carries hf-ink-focus class that enables animated ink border", () => {
    const { container } = render(<Textarea />);
    expect(container.querySelector("textarea")!.className).toMatch(/hf-ink-focus/);
  });
});

describe("Textarea — invalid state", () => {
  it("renders with aria-invalid when passed", () => {
    const { container } = render(<Textarea aria-invalid="true" />);
    expect(container.querySelector("textarea")).toHaveAttribute("aria-invalid", "true");
  });

  it("applies danger border class when aria-invalid", () => {
    const { container } = render(<Textarea aria-invalid="true" />);
    const el = container.querySelector("textarea")!;
    expect(el.className).toMatch(/aria-invalid:border-hf-danger/);
  });
});

describe("Textarea — char cap counter", () => {
  it("does NOT render counter when maxLength not provided", () => {
    const { container } = render(<Textarea />);
    expect(container.querySelector("[data-slot='char-cap']")).toBeNull();
  });

  it("renders counter when maxLength is provided", () => {
    const { container } = render(<Textarea maxLength={2000} defaultValue="hello" />);
    expect(container.querySelector("[data-slot='char-cap']")).toBeTruthy();
  });

  it("counter shows 'n / max' format matching value length", () => {
    const { container } = render(<Textarea maxLength={2000} defaultValue="hello" />);
    const counter = container.querySelector("[data-slot='char-cap']")!;
    expect(counter.textContent).toMatch(/5\s*\/\s*2,000/);
  });

  it("counter updates as user types", () => {
    const { container } = render(<Textarea maxLength={2000} defaultValue="" />);
    const ta = container.querySelector("textarea")!;
    fireEvent.change(ta, { target: { value: "hello world" } });
    const counter = container.querySelector("[data-slot='char-cap']")!;
    expect(counter.textContent).toMatch(/11\s*\/\s*2,000/);
  });

  it("counter uses comma-formatted max (2,000)", () => {
    const { container } = render(<Textarea maxLength={2000} defaultValue="" />);
    const counter = container.querySelector("[data-slot='char-cap']")!;
    expect(counter.textContent).toMatch(/2,000/);
  });

  it("renders wrapper div when maxLength present", () => {
    const { container } = render(<Textarea maxLength={100} defaultValue="x" />);
    expect(container.querySelector("div")).toBeTruthy();
  });
});
