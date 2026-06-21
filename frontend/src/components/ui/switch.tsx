"use client";

import * as React from "react";
import { Switch as SwitchPrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

/**
 * Switch (big pill toggle) — theme-aware on/off contrast.
 *
 * Light:
 *   OFF track = neutral warm   (--hf-switch-track-off = --hf-neutral-300)
 *   ON  track = ink            (--hf-fg-1 = #1a1a1a)
 *   knob      = white surface  (--hf-surface = #fff, both states)
 *
 * Dark:
 *   OFF track = warm mid-dark  (--hf-switch-track-off = #38332b, token overridden in .dark)
 *   ON  track = paper/light    (--hf-fg-1 = #f2eee6 in dark — same class, token re-resolves)
 *   OFF knob  = light warm     (--hf-fg-2 = #cfc8bc in dark)
 *   ON  knob  = dark ink       (--hf-bg   = #14130f in dark)
 *
 * CSS transition on the knob handles reduced-motion at the blanket @layer base guard in
 * index.css — no per-component reduced-motion override needed.
 */
function Switch({
  className,
  size = "default",
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root> & {
  size?: "sm" | "default";
}) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      data-size={size}
      className={cn(
        // Layout + shape
        "peer group/switch inline-flex shrink-0 items-center rounded-full",
        // Sizing by data-size (height × width matching the 30px × 52px mockup spec)
        "data-[size=default]:h-[1.875rem] data-[size=default]:w-[3.25rem]",
        "data-[size=sm]:h-5 data-[size=sm]:w-9",
        // Track colours — token-based, re-resolve under .dark automatically
        "bg-hf-switch-track-off",
        "data-[state=checked]:bg-hf-fg-1",
        // Transition (track colour fades)
        "transition-colors duration-[var(--duration-2)] ease-[var(--ease)]",
        // Focus ring (Task 4 contract — soft ring, no border change)
        "outline-none",
        "focus-visible:ring-hf-fg-1/40 focus-visible:ring-2",
        "focus-visible:ring-offset-hf-bg focus-visible:ring-offset-2",
        // Disabled
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className={cn(
          // Shape
          "pointer-events-none block rounded-full",
          // Sizing: 24px for default, 16px for sm (3px inset each side from mockup)
          "group-data-[size=default]/switch:size-6",
          "group-data-[size=sm]/switch:size-4",
          // Translate: unchecked = 3px from left edge; checked = right-aligned with 3px inset
          "data-[state=unchecked]:translate-x-[3px]",
          "data-[state=checked]:group-data-[size=default]/switch:translate-x-[calc(3.25rem-1.875rem+3px)]",
          "data-[state=checked]:group-data-[size=sm]/switch:translate-x-[calc(2.25rem-1.25rem+1px)]",
          // Knob colour — light: white (hf-surface) in both ON and OFF states
          "bg-hf-surface",
          // Knob colour — dark: light warm knob OFF, dark ink knob ON
          "dark:bg-hf-fg-2",
          "dark:data-[state=checked]:bg-hf-bg",
          // Elevation shadow
          "shadow-[0_1px_3px_rgba(0,0,0,0.25)]",
          // Transition (transform slide + colour change)
          "transition-[transform,background-color] duration-[var(--duration-2)] ease-[var(--ease)]",
        )}
      />
    </SwitchPrimitive.Root>
  );
}

export { Switch };
