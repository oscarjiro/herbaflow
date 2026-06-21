"use client";

import * as React from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { Select as SelectPrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

function Select({ ...props }: React.ComponentProps<typeof SelectPrimitive.Root>) {
  return <SelectPrimitive.Root data-slot="select" {...props} />;
}

function SelectGroup({ ...props }: React.ComponentProps<typeof SelectPrimitive.Group>) {
  return <SelectPrimitive.Group data-slot="select-group" {...props} />;
}

function SelectValue({ ...props }: React.ComponentProps<typeof SelectPrimitive.Value>) {
  return <SelectPrimitive.Value data-slot="select-value" {...props} />;
}

function SelectTrigger({
  className,
  size = "default",
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {
  size?: "sm" | "default";
}) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      data-size={size}
      className={cn(
        // Layout + sizing
        "group flex w-full items-center justify-between gap-2 whitespace-nowrap",
        "data-[size=default]:h-9 data-[size=sm]:h-8",
        "px-3 py-2",
        // SOLID surface — no glass on form controls (spec §5.1 + §9.3)
        "bg-hf-surface border-hf-border-strong border",
        // Small radius matching input (spec §3.2 --radius-sm = 8px)
        "rounded-sm",
        // Typography
        "text-hf-fg-1 text-sm",
        "data-[placeholder]:text-hf-fg-4",
        // Animated ink-border focus — reuse Task 6 utility, NO ring
        "hf-ink-focus",
        "outline-none",
        // Suppress default :where(input,select,textarea):focus-visible from index.css
        "focus-visible:outline-none",
        // Value slot layout
        "*:data-[slot=select-value]:line-clamp-1",
        "*:data-[slot=select-value]:flex",
        "*:data-[slot=select-value]:items-center",
        "*:data-[slot=select-value]:gap-2",
        // Icon slot
        "[&_svg]:pointer-events-none [&_svg]:shrink-0",
        // Disabled
        "disabled:cursor-not-allowed disabled:opacity-50",
        // Invalid — reuse hf-ink-focus invalid path
        "aria-invalid:border-hf-danger",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        {/*
         * Chevron rotates 180° when the select is open.
         * The trigger carries `data-state="open"` (set by Radix). We use Tailwind's
         * `group-data-[state=open]:` variant so the chevron responds to parent state.
         * `data-[state=open]:rotate-180` is also added directly for when Radix passes
         * the state down through asChild slot composition.
         */}
        <ChevronDownIcon
          className={cn(
            "text-hf-fg-3 size-4 shrink-0",
            "transition-transform duration-[var(--duration-2,230ms)] ease-[var(--ease-out)]",
            "group-data-[state=open]:rotate-180",
            "data-[state=open]:rotate-180",
          )}
        />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

function SelectContent({
  className,
  children,
  position = "item-aligned",
  align = "center",
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        data-slot="select-content"
        className={cn(
          // Solid panel — SOLID tier (not glass); readability over effect (spec §5.1)
          "bg-hf-surface text-hf-fg-1",
          // Border + radius + shadow
          "border-hf-border rounded-md border",
          "shadow-[var(--hf-glass-shadow,0_8px_24px_rgba(0,0,0,0.12))]",
          // Positioning
          "relative z-50",
          "min-w-[8rem]",
          "max-h-[var(--radix-select-content-available-height)]",
          "origin-[var(--radix-select-content-transform-origin)]",
          // Internal scroll — reuse .scroll utility (Task 4: thin styled scrollbar)
          "scroll overflow-x-hidden overflow-y-auto",
          // Entrance animation — scale + fade via Radix data-state + Tailwind animate-*
          // Closed → open: fade in + scale from 0.95 to 1
          "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          // Open → closed: fade out + scale down
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          // Side slide-in for positional polish
          "data-[side=bottom]:slide-in-from-top-2",
          "data-[side=left]:slide-in-from-right-2",
          "data-[side=right]:slide-in-from-left-2",
          "data-[side=top]:slide-in-from-bottom-2",
          position === "popper" &&
            "data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1",
          className,
        )}
        position={position}
        align={align}
        {...props}
      >
        <SelectScrollUpButton />
        <SelectPrimitive.Viewport
          className={cn(
            "p-1",
            position === "popper" &&
              "h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)] scroll-my-1",
          )}
        >
          {children}
        </SelectPrimitive.Viewport>
        <SelectScrollDownButton />
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

function SelectLabel({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.Label>) {
  return (
    <SelectPrimitive.Label
      data-slot="select-label"
      className={cn("text-hf-fg-3 px-2 py-1.5 text-xs font-medium", className)}
      {...props}
    />
  );
}

function SelectItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        // Layout
        "relative flex w-full cursor-default items-center gap-2",
        "py-2 pr-8 pl-2",
        // Radius + typography
        "text-hf-fg-1 rounded-sm text-sm",
        // Hover / focus — subtle surface-2 highlight (visible keyboard focus)
        "hover:bg-hf-surface-2 focus:bg-hf-surface-2",
        // Keep Radix a11y: visible focus outline for keyboard users (WCAG 2.2)
        "outline-none focus-visible:outline-none",
        // Disabled
        "select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className,
      )}
      {...props}
    >
      {/* Selected dot indicator — right-aligned, matches mockup .csel__opt .ind */}
      <span
        data-slot="select-item-indicator"
        className="absolute right-2 flex size-4 items-center justify-center"
      >
        <SelectPrimitive.ItemIndicator>
          {/* Filled dot: 7px pill, accent colour (--hf-fg-1), matching mockup */}
          <span
            className="hf-select-dot bg-hf-fg-1 block size-[7px] rounded-[var(--radius-pill)]"
            aria-hidden="true"
          />
        </SelectPrimitive.ItemIndicator>
      </span>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  );
}

function SelectSeparator({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Separator>) {
  return (
    <SelectPrimitive.Separator
      data-slot="select-separator"
      className={cn("bg-hf-border pointer-events-none -mx-1 my-1 h-px", className)}
      {...props}
    />
  );
}

function SelectScrollUpButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollUpButton>) {
  return (
    <SelectPrimitive.ScrollUpButton
      data-slot="select-scroll-up-button"
      className={cn("text-hf-fg-3 flex cursor-default items-center justify-center py-1", className)}
      {...props}
    >
      <ChevronUpIcon className="size-4" />
    </SelectPrimitive.ScrollUpButton>
  );
}

function SelectScrollDownButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollDownButton>) {
  return (
    <SelectPrimitive.ScrollDownButton
      data-slot="select-scroll-down-button"
      className={cn("text-hf-fg-3 flex cursor-default items-center justify-center py-1", className)}
      {...props}
    >
      <ChevronDownIcon className="size-4" />
    </SelectPrimitive.ScrollDownButton>
  );
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
};
