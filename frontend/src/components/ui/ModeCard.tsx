import * as React from "react";
import { CheckIcon } from "lucide-react";

import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ModeCardProps {
  /** Unique identifier for this card within the group. Passed back to onSelect. */
  id: string;
  /** Primary label displayed in the card header. */
  title: string;
  /** Supporting description below the title. */
  description: string;
  /** Optional icon rendered above the title. */
  icon?: React.ReactNode;
  /** Whether this card is currently selected. */
  selected: boolean;
  /** Called with this card's id when the user activates it. */
  onSelect: (id: string) => void;
  /** Optional additional class names for the card element. */
  className?: string;
}

export interface ModeCardGroupProps {
  children: React.ReactNode;
  className?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
}

// ---------------------------------------------------------------------------
// ModeCardGroup — wraps cards in a radiogroup
// ---------------------------------------------------------------------------

/**
 * ModeCardGroup — semantic container for a set of ModeCards.
 *
 * Provides the ARIA radiogroup role so screen readers announce the
 * selection pattern. Always pass aria-label or aria-labelledby.
 */
function ModeCardGroup({ children, className, ...props }: ModeCardGroupProps) {
  return (
    <div role="radiogroup" className={cn("flex flex-col gap-3 sm:flex-row", className)} {...props}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ModeCard — selectable option card
// ---------------------------------------------------------------------------

/**
 * ModeCard — solid, selectable option card for choosing analysis modes.
 *
 * Selection is communicated by a brighter, elevated card body (raised surface
 * + glass shadow) PLUS a filled lucide CheckIcon in the tick badge. No tint,
 * no colored ring, no border change signals selection — elevation alone does.
 *
 * Light theme: unselected = hf-surface-2; selected = hf-surface (brighter).
 * Dark theme: reversed via Tailwind `dark:` prefix.
 *
 * Hover: subtle translateY(-2px) lift with border warming to hf-fg-4.
 * Reduced-motion: handled by the global @media guard already in index.css.
 *
 * A11y: role="radio" + aria-checked; keyboard Space/Enter activate;
 * focus ring uses focus-visible:ring-hf-fg-1/40 (soft ring, no border change).
 */
function ModeCard({ id, title, description, icon, selected, onSelect, className }: ModeCardProps) {
  function handleClick() {
    onSelect(id);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      onSelect(id);
    }
  }

  return (
    <div
      role="radio"
      aria-checked={selected}
      aria-label={title}
      tabIndex={0}
      data-slot="mode-card"
      data-selected={selected ? "true" : "false"}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        // Shape + padding — matches mockup r-lg = 16px = rounded-[var(--radius-lg)]
        "relative cursor-pointer rounded-[var(--radius-lg)] border p-[18px]",
        // Transitions: transform + background + border-color + box-shadow
        "transition-[transform,background-color,border-color,box-shadow]",
        "duration-[var(--duration-2)] ease-[var(--ease)]",
        // Resting body — light: surface-2 (dimmer); dark: surface
        "border-hf-border bg-hf-surface-2",
        "dark:bg-hf-surface",
        // Hover: lift + border warming (no bg change on hover in the fixes mockup)
        "hover:border-hf-fg-4 hover:-translate-y-0.5",
        // Selected: brighter elevated body (light: surface; dark: surface-2) + glass shadow
        // NO ring, NO colored border, NO tint — elevation + check only
        selected && ["bg-hf-surface shadow-[var(--hf-glass-shadow)]", "dark:bg-hf-surface-2"],
        // Focus ring — soft ring, no border-color change
        "outline-none",
        "focus-visible:ring-hf-fg-1/40 focus-visible:ring-2",
        "focus-visible:ring-offset-hf-bg focus-visible:ring-offset-2",
        className,
      )}
    >
      {/* Optional icon slot */}
      {icon != null && (
        <div data-slot="mode-card-icon" className="text-hf-fg-2 mb-3">
          {icon}
        </div>
      )}

      {/* Title row with tick badge */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-hf-fg-1 text-sm leading-none font-semibold select-none">{title}</span>

        {/* Tick — pill shape, 20x20. Selected: filled ink. Unselected: border only. */}
        <span
          data-slot="mode-card-tick"
          aria-hidden="true"
          className={cn(
            // Size + shape (pill — matches mockup 20x20 border-radius 999px)
            "inline-flex h-5 w-5 flex-none items-center justify-center rounded-full",
            // Transition on all properties
            "transition-all duration-[var(--duration-2)] ease-[var(--ease)]",
            // Unselected: border-only, icon transparent
            !selected && ["border-hf-border-strong border", "bg-transparent text-transparent"],
            // Selected: filled ink background, icon in bg color
            selected && ["border-hf-fg-1 bg-hf-fg-1 text-hf-bg border"],
          )}
        >
          <CheckIcon className="h-[13px] w-[13px]" strokeWidth={2.4} />
        </span>
      </div>

      {/* Description */}
      <p className="text-hf-fg-2 mt-1.5 text-[12.5px] leading-relaxed select-none">{description}</p>
    </div>
  );
}

export { ModeCard, ModeCardGroup };
