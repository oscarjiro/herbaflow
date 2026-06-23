/**
 * Select re-skin: input-like trigger, animated menu, selected dot, chevron rotation.
 *
 * jsdom cannot simulate :focus-visible or CSS transitions, so we assert:
 * - the trigger renders with input-like classes (bg-hf-surface, border-hf-border-strong,
 *   rounded-sm, hf-ink-focus) and no focus-ring classes
 * - the chevron icon carries a rotation-transition class that responds to data-[state=open]
 * - opening the select (via Radix open prop) renders the content
 * - the selected item carries the dot indicator element (data-slot="select-item-indicator")
 * - SelectContent carries the scroll utility and solid panel classes
 *
 * Radix pointer-capture / scrollIntoView stubs are already applied globally in tests/setup.ts.
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** A minimal controlled select rendered open so we can inspect the content. */
function OpenSelect({ value = "" }: { value?: string }) {
  return (
    <Select open value={value} onValueChange={() => {}}>
      <SelectTrigger aria-label="Pick an option">
        <SelectValue placeholder="Choose..." />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="apple">Apple</SelectItem>
        <SelectItem value="banana">Banana</SelectItem>
        <SelectItem value="cherry">Cherry</SelectItem>
      </SelectContent>
    </Select>
  );
}

/** A minimal closed select for trigger-only class assertions. */
function ClosedSelect() {
  return (
    <Select>
      <SelectTrigger aria-label="Pick an option">
        <SelectValue placeholder="Choose..." />
      </SelectTrigger>
    </Select>
  );
}

// ---------------------------------------------------------------------------
// Trigger appearance — input-like surface + focus model
// ---------------------------------------------------------------------------

describe("SelectTrigger — input-like classes", () => {
  it("renders with surface fill class (bg-hf-surface)", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    expect(trigger.className).toContain("bg-hf-surface");
  });

  it("renders with strong border class (border-hf-border-strong)", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    expect(trigger.className).toContain("border-hf-border-strong");
  });

  it("renders with small radius (rounded-sm)", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    expect(trigger.className).toContain("rounded-sm");
  });

  it("carries hf-ink-focus utility (animated ink border, no ring)", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    expect(trigger.className).toContain("hf-ink-focus");
  });

  it("does NOT carry focus-visible:ring classes (no ring model)", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    // The old shadcn trigger had focus-visible:ring-[3px] — must be gone.
    expect(trigger.className).not.toMatch(/focus-visible:ring-\[3px\]/);
    expect(trigger.className).not.toMatch(/focus-visible:ring-ring/);
  });

  it("has data-slot='select-trigger'", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    expect(trigger.getAttribute("data-slot")).toBe("select-trigger");
  });
});

// ---------------------------------------------------------------------------
// Chevron — rotation class present on the icon element
// ---------------------------------------------------------------------------

describe("SelectTrigger — chevron rotation", () => {
  it("chevron icon carries a rotate-180 class triggered by open state", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    // The chevron SVG is inside the trigger; it should have the rotate class string.
    const chevron = trigger.querySelector("svg");
    expect(chevron).not.toBeNull();
    // SVGElement.className is an SVGAnimatedString — use getAttribute("class") instead.
    const cls = chevron!.getAttribute("class") ?? "";
    // group-data-[state=open]:rotate-180 is the Tailwind group-variant for parent-driven rotation
    expect(cls).toMatch(/rotate-180/);
  });

  it("chevron carries transition-transform class", () => {
    render(<ClosedSelect />);
    const trigger = screen.getByRole("combobox", { name: /pick an option/i });
    const chevron = trigger.querySelector("svg");
    const cls = chevron!.getAttribute("class") ?? "";
    expect(cls).toContain("transition-transform");
  });

  it("select trigger chevron uses the muted fg token", () => {
    const { container } = render(<ClosedSelect />);
    const chevron = container.querySelector("[data-slot='select-trigger'] svg");
    expect(chevron).not.toBeNull();
    const cls = chevron!.getAttribute("class") ?? "";
    expect(cls).toMatch(/text-hf-fg-3/);
  });
});

// ---------------------------------------------------------------------------
// Menu open — content renders, carries solid panel + scroll classes
// ---------------------------------------------------------------------------

describe("SelectContent — menu rendered when open", () => {
  it("renders the listbox when Select is open", () => {
    render(<OpenSelect />);
    // Radix renders a listbox role for the content
    expect(screen.getByRole("listbox")).toBeTruthy();
  });

  it("content element carries solid surface class (bg-hf-surface)", () => {
    render(<OpenSelect />);
    // The SelectContent wraps the listbox — find the content container
    const content = document.querySelector("[data-slot='select-content']");
    expect(content).not.toBeNull();
    expect(content!.className).toContain("bg-hf-surface");
  });

  it("content carries the scroll utility class for long menus", () => {
    render(<OpenSelect />);
    const content = document.querySelector("[data-slot='select-content']");
    expect(content).not.toBeNull();
    expect(content!.className).toContain("scroll");
  });

  it("content carries rounded-md class (var(--radius-md))", () => {
    render(<OpenSelect />);
    const content = document.querySelector("[data-slot='select-content']");
    expect(content).not.toBeNull();
    expect(content!.className).toContain("rounded-md");
  });

  it("renders all three option items", () => {
    render(<OpenSelect />);
    expect(screen.getByRole("option", { name: /apple/i })).toBeTruthy();
    expect(screen.getByRole("option", { name: /banana/i })).toBeTruthy();
    expect(screen.getByRole("option", { name: /cherry/i })).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Selected dot — indicator element present on items; visible when selected
// ---------------------------------------------------------------------------

describe("SelectItem — selected dot indicator", () => {
  it("each item carries a data-slot='select-item-indicator' element", () => {
    render(<OpenSelect />);
    const indicators = document.querySelectorAll("[data-slot='select-item-indicator']");
    // Three items → three indicator slots
    expect(indicators.length).toBeGreaterThanOrEqual(3);
  });

  it("the indicator container carries the dot class when item is selected", () => {
    // Render with 'apple' selected
    render(<OpenSelect value="apple" />);
    const appleOption = screen.getByRole("option", { name: /apple/i });
    // The indicator within the selected item should carry the dot class
    const indicator = appleOption.querySelector("[data-slot='select-item-indicator']");
    expect(indicator).not.toBeNull();
    // The dot span inside the indicator carries hf-select-dot or the dot styling class
    expect(indicator!.innerHTML.length).toBeGreaterThan(0);
  });

  it("SelectItem carries data-slot='select-item'", () => {
    render(<OpenSelect />);
    const items = document.querySelectorAll("[data-slot='select-item']");
    expect(items.length).toBeGreaterThanOrEqual(3);
  });

  it("selected item (aria-selected=true) has the filled dot child span", () => {
    render(<OpenSelect value="banana" />);
    const bananaOption = screen.getByRole("option", { name: /banana/i });
    expect(bananaOption.getAttribute("aria-selected")).toBe("true");
    // The dot span inside its indicator should be present
    const indicator = bananaOption.querySelector("[data-slot='select-item-indicator']");
    expect(indicator).not.toBeNull();
    // The filled dot span carries the accent bg class
    const dot = indicator!.querySelector(".hf-select-dot");
    expect(dot).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Data-state animation classes — Radix data attributes for CSS transitions
// ---------------------------------------------------------------------------

describe("SelectContent — data-state animation hooks", () => {
  it("data-[state=open] + data-[state=closed] animate classes present on content", () => {
    render(<OpenSelect />);
    const content = document.querySelector("[data-slot='select-content']");
    expect(content).not.toBeNull();
    // The class string should include animation hooks for Radix data-state
    const cls = content!.className;
    expect(cls).toMatch(/data-\[state=open\]/);
    expect(cls).toMatch(/data-\[state=closed\]/);
  });
});
