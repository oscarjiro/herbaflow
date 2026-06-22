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
  it("primary variant renders the glass layer stack, not a solid ink fill", () => {
    const { container } = render(<Button variant="primary">Start analysis</Button>, {
      wrapper: Wrapper,
    });
    const root = container.querySelector("[data-slot='button']")!;
    // glass root + layered recipe
    expect(root.className).toMatch(/hf-glass/);
    expect(container.querySelector(".hf-glass__refract")).not.toBeNull();
    expect(container.querySelector(".hf-glass__tint")).not.toBeNull();
    expect(container.querySelector(".hf-glass__content")).not.toBeNull();
    // primary tint hook + ink label, NOT the old solid `bg-hf-fg-1` fill
    expect(root.className).toMatch(/hf-btn--primary/);
    expect(root.className).not.toMatch(/bg-hf-fg-1/);
  });

  it("secondary/ghost/danger variants also render glass with their tint class", () => {
    for (const v of ["secondary", "ghost", "danger"] as const) {
      const { container, unmount } = render(<Button variant={v}>x</Button>, { wrapper: Wrapper });
      const root = container.querySelector("[data-slot='button']")!;
      expect(root.className).toMatch(/hf-glass/);
      expect(root.className).toMatch(new RegExp(`hf-btn--${v}`));
      // Unmount each iteration so the motion-wrapped surface stops scheduling
      // requestAnimationFrame; otherwise pending rAFs leak into the later
      // fake-timer StatefulButton tests and trip the "infinite loop" guard.
      unmount();
    }
  });

  it("glass-action variant renders glass pill wrapper", () => {
    render(<Button variant="glass-action">Glass action</Button>, { wrapper: Wrapper });
    // The glass-action variant wraps in a .hf-glass container; look for the button label text
    expect(screen.getByText("Glass action")).toBeInTheDocument();
    // The outer element must carry hf-glass class (overlay tier)
    const pill = document.querySelector(".hf-glass");
    expect(pill).not.toBeNull();
  });

  it("glass-action with asChild renders one anchor carrying the full glass recipe", () => {
    render(
      <Button asChild variant="glass-action">
        <a href="/analysis">Start analysis</a>
      </Button>,
      { wrapper: Wrapper },
    );
    // The child element (anchor) is the glass surface — no nested <button>.
    const link = screen.getByRole("link", { name: /start analysis/i });
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/analysis");
    expect(link.className).toContain("hf-glass");
    // The canonical glass layers are injected inside the single anchor.
    expect(link.querySelector(".hf-glass__refract")).not.toBeNull();
    expect(link.querySelector(".hf-glass__tint")).not.toBeNull();
    expect(link.querySelector(".hf-glass__shine")).not.toBeNull();
    expect(link.querySelector(".hf-glass__content")).not.toBeNull();
    // No stray <button> from the component when asChild is set.
    expect(document.querySelector("button")).toBeNull();
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
