/**
 * StatefulButton — idle → loading → success → reset
 *
 * Driven by an async `onClickAsync` prop. State transitions:
 *  idle   → user clicks → loading (spinner + "Working…")
 *  loading → promise resolves → success (✓ Done)
 *  success → after `successDuration` ms → idle (reset)
 *
 * Animation uses Motion (`m.*` from `motion/react`; LazyMotion is already
 * provided app-wide in __root.tsx). Respects `prefers-reduced-motion`:
 * when reduced motion is on, the spinner and check-mark still appear but
 * the animated entrance/exit is suppressed (duration → 0ms).
 *
 * Accessibility:
 *  - `aria-busy="true"` during loading
 *  - `aria-live="polite"` region announces state to screen readers
 *  - pointer-events: none while loading or success (prevents double-click)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { m, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

type ButtonState = "idle" | "loading" | "success";

interface StatefulButtonProps extends Omit<React.ComponentProps<"button">, "onClick"> {
  /** Async handler called on click. When the promise resolves, the button
   *  transitions to the success state. If omitted the button still renders
   *  but clicking it is a no-op (useful for storybook / controlled usage). */
  onClickAsync?: () => Promise<void>;
  /** How long (ms) to stay in the success state before resetting. Default 1800. */
  successDuration?: number;
}

export function StatefulButton({
  children,
  className,
  onClickAsync,
  successDuration = 1800,
  disabled,
  ...props
}: StatefulButtonProps) {
  const [state, setState] = useState<ButtonState>("idle");
  const shouldReduceMotion = useReducedMotion();
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up any pending reset timer on unmount.
  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) clearTimeout(resetTimerRef.current);
    };
  }, []);

  const handleClick = useCallback(async () => {
    if (!onClickAsync || state !== "idle") return;

    setState("loading");
    try {
      await onClickAsync();
    } finally {
      setState("success");
      resetTimerRef.current = setTimeout(() => {
        setState("idle");
      }, successDuration);
    }
  }, [onClickAsync, state, successDuration]);

  const isLoading = state === "loading";
  const isSuccess = state === "success";
  const isBusy = isLoading || isSuccess;

  // Motion config — zero duration when reduced-motion is active so state
  // still changes but there is no perceptible animation.
  const dur = shouldReduceMotion ? 0 : 0.18;

  return (
    <div className="relative inline-flex flex-col items-start">
      <button
        type="button"
        aria-busy={isLoading ? "true" : undefined}
        disabled={disabled}
        onClick={handleClick}
        className={cn(
          // Base: same as `primary` variant (ink pill) + min-width for stable layout
          "inline-flex min-w-[168px] items-center justify-center gap-2",
          "rounded-[var(--radius-pill)] px-5 py-2.5 text-sm font-medium",
          "bg-hf-fg-1 text-hf-bg",
          "transition-all outline-none",
          "focus-visible:ring-ring/50 focus-visible:ring-[3px]",
          "disabled:pointer-events-none disabled:opacity-45",
          // Prevent interaction while busy
          isBusy && "pointer-events-none",
          // Success: sage tint to signal completion
          isSuccess && "bg-hf-success text-hf-bg",
          className,
        )}
        {...props}
      >
        <m.span
          key={state}
          initial={shouldReduceMotion ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: dur, ease: [0.2, 0.7, 0.2, 1] }}
          className="inline-flex items-center gap-2"
        >
          {isLoading && (
            <>
              <Spinner />
              <span>Working…</span>
            </>
          )}
          {isSuccess && (
            <>
              <CheckIcon />
              <span>Done</span>
            </>
          )}
          {state === "idle" && children}
        </m.span>
      </button>

      {/* Visually hidden aria-live region — announces state changes to screen readers. */}
      <span aria-live="polite" aria-atomic="true" className="sr-only">
        {isLoading ? "Working, please wait." : isSuccess ? "Done." : ""}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal micro-components
// ---------------------------------------------------------------------------

/** Animated spinner ring — matches .ring in primitives-v2.html */
function Spinner() {
  const shouldReduceMotion = useReducedMotion();
  return (
    <span
      aria-hidden="true"
      className={cn(
        "block size-[15px] rounded-full",
        "border-t-hf-bg border-2 border-[color-mix(in_srgb,var(--hf-bg),transparent_55%)]",
        !shouldReduceMotion && "animate-spin",
      )}
      style={
        shouldReduceMotion
          ? undefined
          : { animationDuration: "0.7s", animationTimingFunction: "linear" }
      }
    />
  );
}

/** Check mark icon for the success state. */
function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="2,7 5.5,11 12,3" />
    </svg>
  );
}
