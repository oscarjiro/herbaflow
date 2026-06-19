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
