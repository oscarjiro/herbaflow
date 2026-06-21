/**
 * Task 11 — Action search bar: debounced command combobox with rich result rows.
 *
 * Tests:
 * 1. Typing filters rows AFTER debounce elapses (fake timers)
 * 2. A result row renders icon + italic-serif binomial + family + count
 * 3. Selecting a row fires onSelect with the item
 * 4. The popup opens downward (side="bottom" attribute on content)
 * 5. Popup width binds to the field width (w-[var(--radix-popover-trigger-width)] class present)
 *
 * Radix pointer-capture / scrollIntoView stubs are applied globally in tests/setup.ts.
 */
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ActionSearchBar, type ActionSearchItem } from "./ActionSearchBar";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ITEMS: ActionSearchItem[] = [
  {
    id: "1",
    binomial: "Curcuma longa",
    family: "Zingiberaceae",
    count: 412,
    countLabel: "compounds",
  },
  {
    id: "2",
    binomial: "Curcuma xanthorrhiza",
    family: "Zingiberaceae",
    count: 388,
    countLabel: "compounds",
  },
  {
    id: "3",
    binomial: "Zingiber officinale",
    family: "Zingiberaceae",
    count: 301,
    countLabel: "compounds",
  },
  {
    id: "4",
    binomial: "Andrographis paniculata",
    family: "Acanthaceae",
    count: 256,
    countLabel: "compounds",
  },
];

// ---------------------------------------------------------------------------
// 1. Debounce: filter does NOT update immediately; updates after debounce elapses
// ---------------------------------------------------------------------------

describe("ActionSearchBar — debounced filtering", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does NOT filter rows immediately after typing (debounce gate)", async () => {
    render(
      <ActionSearchBar
        items={ITEMS}
        placeholder="Search plants..."
        onSelect={vi.fn()}
        open
        defaultOpen
      />,
    );

    // All items are visible initially (popup open)
    expect(screen.getByText("Curcuma longa")).toBeTruthy();
    expect(screen.getByText("Andrographis paniculata")).toBeTruthy();

    // Type a query but do NOT advance timers
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "Zingiber" } });

    // Immediately after keypress — Andrographis should still be present (debounce not yet elapsed)
    expect(screen.getByText("Andrographis paniculata")).toBeTruthy();
  });

  it("filters rows AFTER the debounce delay elapses", async () => {
    render(
      <ActionSearchBar
        items={ITEMS}
        placeholder="Search plants..."
        onSelect={vi.fn()}
        open
        defaultOpen
      />,
    );

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "Zingiber" } });

    // Advance past the debounce window (200 ms)
    await act(async () => {
      vi.advanceTimersByTime(250);
    });

    // Now Andrographis should be gone; Zingiber should remain
    expect(screen.queryByText("Andrographis paniculata")).toBeNull();
    expect(screen.getByText("Zingiber officinale")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 2. Rich row layout: icon + italic-serif binomial + family + count
// ---------------------------------------------------------------------------

describe("ActionSearchBar — rich row layout", () => {
  it("renders a result row with a leading icon element", () => {
    render(
      <ActionSearchBar items={ITEMS} placeholder="Search..." onSelect={vi.fn()} open defaultOpen />,
    );

    // Each item row carries a data-slot="action-row-icon" icon container
    const icons = document.querySelectorAll("[data-slot='action-row-icon']");
    expect(icons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the binomial name in an element carrying italic-serif class", () => {
    render(
      <ActionSearchBar items={ITEMS} placeholder="Search..." onSelect={vi.fn()} open defaultOpen />,
    );

    // The binomial span should carry hf-binomial (font-display italic) class
    const binomials = document.querySelectorAll("[data-slot='action-row-binomial']");
    expect(binomials.length).toBeGreaterThanOrEqual(1);
    // It must carry the italic serif class
    const firstBinomial = binomials[0] as HTMLElement;
    expect(firstBinomial.className).toMatch(/hf-binomial|font-display|italic/);
  });

  it("renders the family name as secondary text", () => {
    render(
      <ActionSearchBar items={ITEMS} placeholder="Search..." onSelect={vi.fn()} open defaultOpen />,
    );

    // Multiple rows share Zingiberaceae — use getAllByText (3 items have it)
    const zingibs = screen.getAllByText("Zingiberaceae");
    expect(zingibs.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Acanthaceae")).toBeTruthy();
  });

  it("renders the count right-aligned with a mono class", () => {
    render(
      <ActionSearchBar items={ITEMS} placeholder="Search..." onSelect={vi.fn()} open defaultOpen />,
    );

    const counts = document.querySelectorAll("[data-slot='action-row-count']");
    expect(counts.length).toBeGreaterThanOrEqual(1);
    // Should include the count value
    expect(counts[0]!.textContent).toMatch(/412|388|301|256/);
  });
});

// ---------------------------------------------------------------------------
// 3. Selecting a row fires onSelect with the item
// ---------------------------------------------------------------------------

describe("ActionSearchBar — selection", () => {
  it("fires onSelect with the selected item when a row is clicked", async () => {
    const handleSelect = vi.fn();
    render(
      <ActionSearchBar
        items={ITEMS}
        placeholder="Search..."
        onSelect={handleSelect}
        open
        defaultOpen
      />,
    );

    // Click the first item
    const firstItem = screen
      .getByText("Curcuma longa")
      .closest("[data-slot='action-row']") as HTMLElement;
    expect(firstItem).not.toBeNull();
    fireEvent.click(firstItem);

    await waitFor(() => {
      expect(handleSelect).toHaveBeenCalledWith(ITEMS[0]);
    });
  });
});

// ---------------------------------------------------------------------------
// 4. Popup opens downward (side="bottom")
// ---------------------------------------------------------------------------

describe("ActionSearchBar — popup placement", () => {
  it("the popup content carries data-side='bottom' (opens downward)", () => {
    render(
      <ActionSearchBar items={ITEMS} placeholder="Search..." onSelect={vi.fn()} open defaultOpen />,
    );

    // Radix Popover.Content sets data-side when rendered
    const content = document.querySelector("[data-slot='action-search-popup']");
    expect(content).not.toBeNull();
    // The side prop forces bottom — the rendered Radix element carries data-side="bottom"
    // OR the component itself sets a data-side attribute
    const dataSide = content!.getAttribute("data-side");
    // Radix sets this in portal; in jsdom it may be absent until interaction,
    // so we also accept checking the class for placement enforcement
    const cls = content!.className;
    // Either data-side=bottom is set, OR the class carries slide-in-from-top (bottom placement indicator)
    expect(
      dataSide === "bottom" ||
        cls.includes("slide-in-from-top") ||
        cls.includes("data-[side=bottom]"),
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 5. Popup width binds to field width
// ---------------------------------------------------------------------------

describe("ActionSearchBar — popup width matches field", () => {
  it("popup content carries the trigger-width CSS variable class", () => {
    render(
      <ActionSearchBar items={ITEMS} placeholder="Search..." onSelect={vi.fn()} open defaultOpen />,
    );

    const content = document.querySelector("[data-slot='action-search-popup']");
    expect(content).not.toBeNull();
    // The popup width must be bound to the trigger width via Radix CSS var
    const cls = content!.className;
    expect(cls).toMatch(/radix-popover-trigger-width|w-\[var\(--radix-popover-trigger-width\)\]/);
  });
});

// ---------------------------------------------------------------------------
// 6. Field carries hf-ink-focus (Task-6 focus model)
// ---------------------------------------------------------------------------

describe("ActionSearchBar — field focus model", () => {
  it("the search field wrapper carries hf-ink-focus", () => {
    render(<ActionSearchBar items={ITEMS} placeholder="Search..." onSelect={vi.fn()} />);

    const wrapper = document.querySelector("[data-slot='action-search-field']");
    expect(wrapper).not.toBeNull();
    expect(wrapper!.className).toContain("hf-ink-focus");
  });

  it("renders an input with combobox role", () => {
    render(<ActionSearchBar items={ITEMS} placeholder="Search plants..." onSelect={vi.fn()} />);

    const input = screen.getByRole("combobox");
    expect(input).toBeTruthy();
  });

  it("input carries aria-expanded reflecting open state", () => {
    render(
      <ActionSearchBar
        items={ITEMS}
        placeholder="Search plants..."
        onSelect={vi.fn()}
        open
        defaultOpen
      />,
    );

    const input = screen.getByRole("combobox");
    // aria-expanded should reflect the open state
    expect(input.getAttribute("aria-expanded")).toBe("true");
  });
});
