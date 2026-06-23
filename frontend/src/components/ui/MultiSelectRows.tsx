import * as React from "react";
import { CheckIcon } from "lucide-react";

import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MultiSelectRowItem {
  /** Unique identifier for this row. */
  id: string;
  /** Primary label displayed in the row. */
  label: string;
  /** Optional right-aligned secondary text (e.g. "4 targets"). */
  meta?: string;
}

export interface MultiSelectRowsProps {
  /** The list of items to render. */
  items: MultiSelectRowItem[];
  /** Controlled set of selected item ids. */
  selected: Set<string>;
  /** Called with the new selection set whenever a row is toggled. */
  onChange: (next: Set<string>) => void;
  /** Optional additional class names for the container. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * MultiSelectRows — selectable list rows with hover fill and animated check.
 *
 * Controlled component. Each row toggles its selected state on click or
 * keyboard (Space / Enter). Hover fill uses --hf-surface-2. The check box
 * animates via CSS transition (reduced-motion handled by the global
 * @media (prefers-reduced-motion) guard already in index.css).
 *
 * A11y: rows use role="option" with aria-selected, are keyboard-focusable,
 * and carry a keyboard-only focus ring (focus-visible:ring-hf-fg-1/40).
 */
function MultiSelectRows({ items, selected, onChange, className }: MultiSelectRowsProps) {
  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onChange(next);
  }

  function handleKeyDown(id: string, e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      toggle(id);
    }
  }

  return (
    <div
      data-slot="multi-select-rows"
      role="listbox"
      aria-multiselectable="true"
      className={cn(
        // Container: surface background, border, rounded, clip rows
        "bg-hf-surface border-hf-border overflow-hidden rounded-[var(--radius-md)] border",
        className,
      )}
    >
      {items.map((item, idx) => {
        const isSelected = selected.has(item.id);
        const isLast = idx === items.length - 1;

        return (
          <div
            key={item.id}
            role="option"
            aria-label={item.label}
            aria-selected={isSelected}
            data-selected={isSelected ? "true" : "false"}
            tabIndex={0}
            onClick={() => toggle(item.id)}
            onKeyDown={(e) => handleKeyDown(item.id, e)}
            className={cn(
              // Layout
              "flex cursor-pointer items-center gap-3 px-[14px] py-[11px]",
              // Border between rows (not after last)
              !isLast && "border-hf-border border-b",
              // Hover fill — token only
              "hover:bg-hf-surface-2",
              // Background transition (duration-1 = 120ms, matches mockup --d1)
              "transition-colors duration-[var(--duration-1)] ease-[var(--ease)]",
              // Focus ring — soft ring, no border change
              "outline-none",
              "focus-visible:ring-hf-fg-1/40 focus-visible:ring-2",
              "focus-visible:ring-offset-hf-bg focus-visible:ring-offset-2",
            )}
          >
            {/* Check box — 20x20, border-radius 6px, transitions bg+border+color */}
            <span
              data-slot="row-check"
              aria-hidden="true"
              className={cn(
                // Size and shape (exact mockup values)
                "inline-flex flex-none items-center justify-center",
                "h-5 w-5 rounded-[6px]",
                // Transition on all properties (duration-2 = 220ms = mockup --d2)
                "transition-all duration-[var(--duration-2)] ease-[var(--ease)]",
                // Unselected: transparent icon, border-strong
                !isSelected && [
                  "border-hf-border-strong border",
                  "text-transparent",
                  "bg-transparent",
                ],
                // Selected: filled ink background, icon in bg color
                isSelected && ["border-hf-fg-1 border", "bg-hf-fg-1", "text-hf-bg"],
              )}
            >
              <CheckIcon className="h-3 w-3" strokeWidth={2.5} />
            </span>

            {/* Label */}
            <span className="text-hf-fg-1 text-sm leading-none select-none">{item.label}</span>

            {/* Optional meta slot — right-aligned, monospace, muted */}
            {item.meta != null && (
              <span
                data-slot="row-meta"
                className="text-hf-fg-3 ml-auto font-mono text-xs select-none"
              >
                {item.meta}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export { MultiSelectRows };
