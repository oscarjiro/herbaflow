import { act, render, renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EntitySearchCombobox, type ComboOption } from "./EntitySearchCombobox";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { cleanup } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OPT_A: ComboOption = { value: "a1", label: "Alpha Plant", hint: null };
const OPT_B: ComboOption = { value: "b1", label: "Beta Plant", hint: "beta-alias" };
const OPT_C: ComboOption = { value: "c1", label: "Gamma Plant", hint: null };

// Rich plant option with count + family
const PLANT_RICH: ComboOption = {
  value: "p1",
  label: "Curcuma longa",
  hint: null,
  familyName: "Zingiberaceae",
  count: 1248,
  kind: "plant",
};

// Rich disease option with count
const DISEASE_RICH: ComboOption = {
  value: "d1",
  label: "Type 2 Diabetes Mellitus",
  hint: null,
  count: 1248,
  kind: "disease",
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Open the combobox popover by clicking the trigger button. */
async function openCombobox(ariaLabel: string) {
  await userEvent.click(screen.getByRole("combobox", { name: ariaLabel }));
}

// ---------------------------------------------------------------------------
// Debounce: exactly one search call per settled term
//
// We test the debounce contract via the useDebouncedValue hook directly
// (using renderHook + fake timers). This avoids the Radix Popover animation
// deadlock that occurs when fake timers are active during a click.
// ---------------------------------------------------------------------------

describe("EntitySearchCombobox — debounce (hook-level)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("coalesces rapid updates into one settled value after delayMs", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value, delay }: { value: string; delay: number }) => useDebouncedValue(value, delay),
      { initialProps: { value: "", delay: 300 } },
    );

    expect(result.current).toBe("");

    // Update three times quickly
    rerender({ value: "a", delay: 300 });
    rerender({ value: "al", delay: 300 });
    rerender({ value: "alp", delay: 300 });

    // Before the delay fires, value hasn't changed
    expect(result.current).toBe("");

    // Advance past the debounce window
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Only the last value should be reflected
    expect(result.current).toBe("alp");
  });

  it("fires a new debounce on each distinct settled value", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }: { value: string }) => useDebouncedValue(value, 300),
      { initialProps: { value: "" } },
    );

    // First settle: "foo"
    rerender({ value: "foo" });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("foo");

    // Second settle: "bar"
    rerender({ value: "bar" });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("bar");
  });
});

// ---------------------------------------------------------------------------
// Results rendering
// ---------------------------------------------------------------------------

describe("EntitySearchCombobox — results rendering", () => {
  it("renders canonical label in results", async () => {
    const search = vi.fn().mockResolvedValue([OPT_A, OPT_B]);
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
      />,
    );
    await openCombobox("Search plants");
    // Wait for results
    expect(await screen.findByText("Alpha Plant")).toBeInTheDocument();
    expect(await screen.findByText("Beta Plant")).toBeInTheDocument();
  });

  it("renders matched-alias hint when hint is set", async () => {
    const search = vi.fn().mockResolvedValue([OPT_B]);
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
      />,
    );
    await openCombobox("Search plants");
    expect(await screen.findByText(/matched: beta-alias/i)).toBeInTheDocument();
  });

  it("does NOT render a hint row when hint is null", async () => {
    const search = vi.fn().mockResolvedValue([OPT_A]);
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
      />,
    );
    await openCombobox("Search plants");
    await screen.findByText("Alpha Plant");
    expect(screen.queryByText(/matched:/i)).not.toBeInTheDocument();
  });

  it("shows empty state when search returns no results", async () => {
    const search = vi.fn().mockResolvedValue([]);
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
      />,
    );
    await openCombobox("Search plants");
    expect(await screen.findByText(/no matches/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// single mode
// ---------------------------------------------------------------------------

describe("EntitySearchCombobox — single mode", () => {
  it("selecting an option calls onChange with that option and closes the popover", async () => {
    const search = vi.fn().mockResolvedValue([OPT_A, OPT_B]);
    const onChange = vi.fn();
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[]}
        onChange={onChange}
        search={search}
        ariaLabel="Search disease"
      />,
    );
    await openCombobox("Search disease");
    // Click the cmdk option for Alpha Plant
    const cmdItems = await screen.findAllByRole("option");
    const alphaItem = cmdItems.find((el) => el.textContent?.includes("Alpha Plant"));
    await userEvent.click(alphaItem!);
    expect(onChange).toHaveBeenCalledWith([OPT_A]);
  });

  it("trigger shows the selected label when a value is selected", async () => {
    const search = vi.fn().mockResolvedValue([]);
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[OPT_A]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search disease"
      />,
    );
    expect(screen.getByRole("combobox", { name: "Search disease" })).toHaveTextContent(
      "Alpha Plant",
    );
  });

  it("shows a remove chip for the selected value", async () => {
    const search = vi.fn().mockResolvedValue([]);
    const onChange = vi.fn();
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[OPT_A]}
        onChange={onChange}
        search={search}
        ariaLabel="Search disease"
      />,
    );
    // The chip list should be present
    const chipList = screen.getByRole("list", { name: /selected search disease/i });
    expect(within(chipList).getByText("Alpha Plant")).toBeInTheDocument();
    // Remove button inside the chip list
    const removeBtn = within(chipList).getByRole("button", { name: /remove alpha plant/i });
    await userEvent.click(removeBtn);
    expect(onChange).toHaveBeenCalledWith([]);
  });
});

// ---------------------------------------------------------------------------
// multiple mode
// ---------------------------------------------------------------------------

describe("EntitySearchCombobox — multiple mode", () => {
  it("selecting an option adds it to selected and keeps the popover open", async () => {
    const search = vi.fn().mockResolvedValue([OPT_A, OPT_B]);
    const onChange = vi.fn();
    const { rerender } = render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[]}
        onChange={onChange}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    await openCombobox("Search plants");
    // Click the cmdk option item for Alpha Plant
    const cmdItems = await screen.findAllByRole("option");
    const alphaItem = cmdItems.find((el) => el.textContent?.includes("Alpha Plant"));
    await userEvent.click(alphaItem!);
    expect(onChange).toHaveBeenCalledWith([OPT_A]);

    // Rerender with new selection
    rerender(
      <EntitySearchCombobox
        mode="multiple"
        selected={[OPT_A]}
        onChange={onChange}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );

    // Popover is still open (can still see the other option in the list)
    expect(await screen.findByText("Beta Plant")).toBeInTheDocument();
  });

  it("selecting an already-selected option toggles it off", async () => {
    const search = vi.fn().mockResolvedValue([OPT_A, OPT_B]);
    const onChange = vi.fn();
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[OPT_A]}
        onChange={onChange}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    await openCombobox("Search plants");
    // Wait for command items to appear and pick Alpha Plant by role
    const cmdItems = await screen.findAllByRole("option");
    const alphaItem = cmdItems.find((el) => el.textContent?.includes("Alpha Plant"));
    await userEvent.click(alphaItem!);
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("blocks adding past max and does not call onChange for the blocked click", async () => {
    const search = vi.fn().mockResolvedValue([OPT_A, OPT_B, OPT_C]);
    const onChange = vi.fn();
    // selected = [OPT_A, OPT_B], max = 2 → at cap
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[OPT_A, OPT_B]}
        onChange={onChange}
        search={search}
        ariaLabel="Search plants"
        max={2}
      />,
    );
    await openCombobox("Search plants");
    // OPT_C is unselected and we're at cap — its cmdk item should be disabled
    const cmdItems = await screen.findAllByRole("option");
    const gammaItem = cmdItems.find((el) => el.textContent?.includes("Gamma Plant"));
    expect(gammaItem).toBeDefined();
    // clicking a disabled cmdk item should do nothing (cmdk blocks the onSelect)
    await userEvent.click(gammaItem!);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows all selected options as chips even when not in current search results", async () => {
    const search = vi.fn().mockResolvedValue([]); // results are empty
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[OPT_A, OPT_B]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    // Chips visible without opening the popover
    expect(screen.getByText("Alpha Plant")).toBeInTheDocument();
    expect(screen.getByText("Beta Plant")).toBeInTheDocument();
  });

  it("trigger shows N selected when multiple are chosen", async () => {
    const search = vi.fn().mockResolvedValue([]);
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[OPT_A, OPT_B]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    expect(screen.getByRole("combobox", { name: "Search plants" })).toHaveTextContent("2 selected");
  });

  it("removing a chip calls onChange without that option", async () => {
    const search = vi.fn().mockResolvedValue([]);
    const onChange = vi.fn();
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[OPT_A, OPT_B]}
        onChange={onChange}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /remove alpha plant/i }));
    expect(onChange).toHaveBeenCalledWith([OPT_B]);
  });
});

// ---------------------------------------------------------------------------
// Rich result rows (.sres)
// ---------------------------------------------------------------------------

describe("EntitySearchCombobox — rich result rows (.sres)", () => {
  it("renders plant binomial name, family, and compound count badge", async () => {
    const search = vi.fn().mockResolvedValue([PLANT_RICH]);
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    await openCombobox("Search plants");
    expect(await screen.findByText("Curcuma longa")).toBeInTheDocument();
    expect(await screen.findByText("Zingiberaceae")).toBeInTheDocument();
    expect(await screen.findByText("1,248 compounds")).toBeInTheDocument();
  });

  it("renders disease name and target count badge without family", async () => {
    const search = vi.fn().mockResolvedValue([DISEASE_RICH]);
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search disease"
      />,
    );
    await openCombobox("Search disease");
    expect(await screen.findByText("Type 2 Diabetes Mellitus")).toBeInTheDocument();
    expect(await screen.findByText("1,248 disease targets")).toBeInTheDocument();
    expect(screen.queryByText(/Zingiberaceae/i)).not.toBeInTheDocument();
  });

  it("formats large counts with thousands separators", async () => {
    const search = vi.fn().mockResolvedValue([{ ...PLANT_RICH, count: 10000 }]);
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[]}
        onChange={() => {}}
        search={search}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    await openCombobox("Search plants");
    expect(await screen.findByText("10,000 compounds")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Selected entity cards (.sel-card)
// ---------------------------------------------------------------------------

describe("EntitySearchCombobox — selected entity cards (.sel-card)", () => {
  it("renders selected plant as a card with name, family·count meta, and remove button", () => {
    const onChange = vi.fn();
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[PLANT_RICH]}
        onChange={onChange}
        search={vi.fn().mockResolvedValue([])}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    // Name rendered in the card
    expect(screen.getByText("Curcuma longa")).toBeInTheDocument();
    // Meta line: "Zingiberaceae · 1,248 compounds"
    expect(screen.getByText(/Zingiberaceae/)).toBeInTheDocument();
    expect(screen.getByText(/1,248 compounds/)).toBeInTheDocument();
    // Remove button
    expect(screen.getByRole("button", { name: /remove curcuma longa/i })).toBeInTheDocument();
  });

  it("renders selected disease as a card with name, target count meta, and remove button", () => {
    const onChange = vi.fn();
    render(
      <EntitySearchCombobox
        mode="single"
        selected={[DISEASE_RICH]}
        onChange={onChange}
        search={vi.fn().mockResolvedValue([])}
        ariaLabel="Search disease"
      />,
    );
    // Scope to the sel-card list to avoid matching the trigger button text
    const cardList = screen.getByRole("list", { name: /selected search disease/i });
    expect(within(cardList).getByText("Type 2 Diabetes Mellitus")).toBeInTheDocument();
    expect(within(cardList).getByText(/1,248 disease targets/)).toBeInTheDocument();
    expect(
      within(cardList).getByRole("button", { name: /remove type 2 diabetes mellitus/i }),
    ).toBeInTheDocument();
  });

  it("clicking remove on a sel-card calls onChange without that option", async () => {
    const onChange = vi.fn();
    render(
      <EntitySearchCombobox
        mode="multiple"
        selected={[PLANT_RICH]}
        onChange={onChange}
        search={vi.fn().mockResolvedValue([])}
        ariaLabel="Search plants"
        max={10}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /remove curcuma longa/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
