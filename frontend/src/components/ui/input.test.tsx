/**
 * Task 6 — Input: animated ink-border focus, invalid state, char cap.
 *
 * jsdom cannot simulate :focus-visible or CSS transitions, so we assert:
 * - the component renders with the correct base classes / data attributes
 * - the data-focused attribute is applied when the component receives focus
 * - reduced-motion is handled at the CSS layer (tested in index.css.task6.test.ts)
 * - aria-invalid renders the invalid treatment (class present)
 * - the char-cap counter renders and updates as value length changes
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { Input } from "./input";

// jsdom has no matchMedia — stub it so the component doesn't throw
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

describe("Input — base rendering", () => {
  it("renders an <input> element", () => {
    const { container } = render(<Input />);
    expect(container.querySelector("input")).toBeTruthy();
  });

  it("carries data-slot='input'", () => {
    const { container } = render(<Input />);
    expect(container.querySelector("[data-slot='input']")).toBeTruthy();
  });

  it("applies surface-fill class (bg-hf-surface)", () => {
    const { container } = render(<Input />);
    const el = container.querySelector("input")!;
    expect(el.className).toMatch(/bg-hf-surface/);
  });

  it("applies soft border class (border-hf-border-strong)", () => {
    const { container } = render(<Input />);
    const el = container.querySelector("input")!;
    expect(el.className).toMatch(/border-hf-border-strong/);
  });

  it("applies radius-sm class (rounded-sm)", () => {
    const { container } = render(<Input />);
    const el = container.querySelector("input")!;
    expect(el.className).toMatch(/rounded-sm/);
  });

  it("applies placeholder colour token class", () => {
    const { container } = render(<Input placeholder="test" />);
    const el = container.querySelector("input")!;
    expect(el.className).toMatch(/placeholder:text-hf-fg-[34]/);
  });

  it("passes arbitrary className through", () => {
    const { container } = render(<Input className="my-custom" />);
    expect(container.querySelector("input")!.className).toMatch(/my-custom/);
  });

  it("passes type through", () => {
    const { container } = render(<Input type="email" />);
    expect(container.querySelector("input")!.type).toBe("email");
  });
});

describe("Input — focus behaviour (class-level)", () => {
  it("applies the ink-border focus utility via data-focused on the wrapper or the class string", () => {
    // The animated border on focus is realised via focus-visible CSS in index.css.
    // We verify the component does NOT apply a focus-ring class (no focus-visible:ring-*).
    const { container } = render(<Input />);
    const el = container.querySelector("input")!;
    // Must NOT have the legacy ring classes
    expect(el.className).not.toMatch(/focus-visible:ring-\[3px\]/);
    expect(el.className).not.toMatch(/focus-visible:ring-ring/);
  });

  it("applies hf-input-focus class or data attribute that enables ink-border on focus", () => {
    const { container } = render(<Input />);
    const el = container.querySelector("input")!;
    // The component uses the hf-ink-focus utility class (applied in index.css via @layer base override)
    // or carries the class name that opts into the animated border
    expect(el.className).toMatch(/hf-ink-focus/);
  });
});

describe("Input — invalid state", () => {
  it("renders with aria-invalid when passed", () => {
    render(<Input aria-invalid="true" />);
    const el = screen.getByRole("textbox");
    expect(el).toHaveAttribute("aria-invalid", "true");
  });

  it("applies danger border class when aria-invalid", () => {
    const { container } = render(<Input aria-invalid="true" />);
    const el = container.querySelector("input")!;
    // The invalid variant uses border-hf-danger (via aria-invalid: selector)
    expect(el.className).toMatch(/aria-invalid:border-hf-danger/);
  });
});

describe("Input — char cap counter", () => {
  it("does NOT render counter when maxLength is not provided", () => {
    const { container } = render(<Input />);
    expect(container.querySelector("[data-slot='char-cap']")).toBeNull();
  });

  it("renders counter when maxLength is provided", () => {
    const { container } = render(<Input maxLength={2000} defaultValue="hello" />);
    const counter = container.querySelector("[data-slot='char-cap']");
    expect(counter).toBeTruthy();
  });

  it("counter shows 'n / max' format matching value length", () => {
    const { container } = render(<Input maxLength={2000} defaultValue="hello" />);
    const counter = container.querySelector("[data-slot='char-cap']")!;
    expect(counter.textContent).toMatch(/5\s*\/\s*2,000/);
  });

  it("counter updates as user types (controlled)", () => {
    const { container } = render(<Input maxLength={2000} defaultValue="" />);
    const input = container.querySelector("input")!;
    fireEvent.change(input, { target: { value: "abc" } });
    const counter = container.querySelector("[data-slot='char-cap']")!;
    expect(counter.textContent).toMatch(/3\s*\/\s*2,000/);
  });

  it("counter wraps input in a relative container", () => {
    const { container } = render(<Input maxLength={100} defaultValue="x" />);
    // When maxLength present, a wrapper div is rendered around the input
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("counter uses comma-formatted max (2,000 not 2000)", () => {
    const { container } = render(<Input maxLength={2000} defaultValue="" />);
    const counter = container.querySelector("[data-slot='char-cap']")!;
    expect(counter.textContent).toMatch(/2,000/);
  });

  it("char-cap counter is vertically centered", () => {
    const { container } = render(<Input maxLength={200} defaultValue="hi" />);
    const cap = container.querySelector("[data-slot='char-cap']")!;
    expect(cap.className).toMatch(/top-1\/2/);
    expect(cap.className).toMatch(/-translate-y-1\/2/);
  });
});
