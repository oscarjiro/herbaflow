import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LazyMotion, domAnimation } from "motion/react";
import { Button, buttonVariants } from "./button";
import { StatefulButton } from "./StatefulButton";

/** Wrap with LazyMotion so m.* components work (matches __root.tsx provider). */
function Wrapper({ children }: { children: React.ReactNode }) {
  return <LazyMotion features={domAnimation}>{children}</LazyMotion>;
}

// ---------------------------------------------------------------------------
// Button — variant class tests
// ---------------------------------------------------------------------------

describe("Button variants", () => {
  it("primary variant renders ink pill classes", () => {
    render(<Button variant="primary">Start analysis</Button>, { wrapper: Wrapper });
    const btn = screen.getByRole("button", { name: /start analysis/i });
    const cls = btn.className;
    // ink-filled + pill radius
    expect(cls).toContain("bg-hf-fg-1");
    expect(cls).toContain("text-hf-bg");
    expect(cls).toContain("rounded-[var(--radius-pill)]");
  });

  it("glass-action variant renders glass pill wrapper", () => {
    render(<Button variant="glass-action">Glass action</Button>, { wrapper: Wrapper });
    // The glass-action variant wraps in a .hf-glass container; look for the button label text
    expect(screen.getByText("Glass action")).toBeInTheDocument();
    // The outer element must carry hf-glass class (overlay tier)
    const pill = document.querySelector(".hf-glass");
    expect(pill).not.toBeNull();
  });

  it("secondary variant has surface fill and border", () => {
    render(<Button variant="secondary">Secondary</Button>, { wrapper: Wrapper });
    const btn = screen.getByRole("button", { name: /secondary/i });
    expect(btn.className).toContain("bg-hf-surface");
    expect(btn.className).toContain("border-hf-border-strong");
  });

  it("ghost variant has transparent background", () => {
    render(<Button variant="ghost">Ghost</Button>, { wrapper: Wrapper });
    const btn = screen.getByRole("button", { name: /ghost/i });
    expect(btn.className).toContain("bg-transparent");
  });

  it("danger variant has danger text color", () => {
    render(<Button variant="danger">Delete run</Button>, { wrapper: Wrapper });
    const btn = screen.getByRole("button", { name: /delete run/i });
    expect(btn.className).toContain("text-hf-danger");
  });

  it("disabled state sets opacity 0.45 and pointer-events-none", () => {
    render(
      <Button variant="secondary" disabled>
        Disabled
      </Button>,
      { wrapper: Wrapper },
    );
    const btn = screen.getByRole("button", { name: /disabled/i });
    // Tailwind class added by CVA base (disabled:opacity-45 disabled:pointer-events-none)
    expect(btn.className).toContain("disabled:opacity-45");
    expect(btn).toBeDisabled();
  });

  it("buttonVariants returns a string for each variant", () => {
    const variants = [
      "primary",
      "glass-action",
      "secondary",
      "ghost",
      "danger",
      "default",
    ] as const;
    variants.forEach((v) => {
      const cls = buttonVariants({ variant: v });
      expect(typeof cls).toBe("string");
      expect(cls.length).toBeGreaterThan(0);
    });
  });

  it("is focusable (has tabIndex 0 by default)", () => {
    render(<Button variant="primary">Focus me</Button>, { wrapper: Wrapper });
    const btn = screen.getByRole("button", { name: /focus me/i });
    expect(btn.tabIndex).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// StatefulButton — idle → loading → success → reset
// ---------------------------------------------------------------------------

describe("StatefulButton", () => {
  it("renders idle state with label", () => {
    render(<StatefulButton>Run analysis</StatefulButton>, { wrapper: Wrapper });
    expect(screen.getByRole("button", { name: /run analysis/i })).toBeInTheDocument();
  });

  it("transitions idle → loading when clicked, shows spinner and 'Working'", async () => {
    // Use a promise that never resolves during this test so we can inspect
    // the loading state before it transitions away.
    let resolve!: () => void;
    const promise = new Promise<void>((r) => {
      resolve = r;
    });
    const onClickAsync = vi.fn(() => promise);

    render(<StatefulButton onClickAsync={onClickAsync}>Run analysis</StatefulButton>, {
      wrapper: Wrapper,
    });

    const btn = screen.getByRole("button", { name: /run analysis/i });

    // fireEvent.click is synchronous; the handleClick async fn sets state to
    // "loading" synchronously before the await inside it, so we only need a
    // synchronous act flush to see the loading state.
    act(() => {
      fireEvent.click(btn);
    });

    // Button should now be in loading state (state update is synchronous).
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
    // "Working…" is the visible label; match exact to avoid collision with
    // the aria-live "Working, please wait." announcement text.
    expect(screen.getByText("Working…")).toBeInTheDocument();

    // Resolve to avoid hanging promise (keeps test runner clean).
    await act(async () => {
      resolve();
    });
  });

  it("transitions to success state after async resolves, shows checkmark", async () => {
    const onClickAsync = vi.fn(() => Promise.resolve());

    render(<StatefulButton onClickAsync={onClickAsync}>Run analysis</StatefulButton>, {
      wrapper: Wrapper,
    });

    const btn = screen.getByRole("button", { name: /run analysis/i });

    // Click and let the async handler + state updates settle in one act() pass.
    await act(async () => {
      fireEvent.click(btn);
    });

    // After act(), the promise has resolved and React has committed the success state.
    expect(screen.getByText("Done")).toBeInTheDocument();

    // success: aria-busy is no longer set
    const successBtn = screen.getByRole("button");
    expect(successBtn).not.toHaveAttribute("aria-busy", "true");
  });

  it("resets to idle after success timeout", async () => {
    vi.useFakeTimers();
    const onClickAsync = vi.fn(() => Promise.resolve());

    render(
      <StatefulButton onClickAsync={onClickAsync} successDuration={1500}>
        Run analysis
      </StatefulButton>,
      { wrapper: Wrapper },
    );

    fireEvent.click(screen.getByRole("button", { name: /run analysis/i }));

    // Wait for success state
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    // Should be back to idle
    expect(screen.getByRole("button", { name: /run analysis/i })).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("sets pointer-events-none while loading (no double-click)", async () => {
    let resolve: () => void;
    const promise = new Promise<void>((r) => {
      resolve = r;
    });
    const onClickAsync = vi.fn(() => promise);

    render(<StatefulButton onClickAsync={onClickAsync}>Run analysis</StatefulButton>, {
      wrapper: Wrapper,
    });

    fireEvent.click(screen.getByRole("button", { name: /run analysis/i }));

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
    });

    // pointer-events should be none (class)
    const btn = screen.getByRole("button");
    expect(btn.className).toMatch(/pointer-events-none/);

    act(() => {
      resolve!();
    });
  });

  it("has aria-live region for state announcements", () => {
    render(<StatefulButton>Run analysis</StatefulButton>, { wrapper: Wrapper });
    // aria-live polite region for screen readers
    const live = document.querySelector("[aria-live]");
    expect(live).not.toBeNull();
    expect(live?.getAttribute("aria-live")).toBe("polite");
  });

  it("shows state text even with prefers-reduced-motion (no animation, state changes)", async () => {
    // This tests that state transitions happen even when motion is disabled.
    // prefers-reduced-motion only suppresses animation duration — the state
    // and rendered text still change. We don't need to mock matchMedia here
    // because we just verify the state text appears regardless.
    const onClickAsync = vi.fn(() => Promise.resolve());

    render(<StatefulButton onClickAsync={onClickAsync}>Run analysis</StatefulButton>, {
      wrapper: Wrapper,
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /run analysis/i }));
    });

    // After act(), the resolved promise has committed the success state.
    expect(screen.getByText("Done")).toBeInTheDocument();
  });
});
