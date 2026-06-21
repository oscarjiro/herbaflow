/**
 * ActionSearchBar — debounced command combobox with rich result rows.
 *
 * Spec §9.7: Raycast-style rich rows on the Radix command combobox + Motion.
 * Each row: leaf icon, binomial name (italic serif), family, and a count.
 * Debounced; opens downward; popup width matches the field.
 *
 * Uses:
 * - Radix Popover (side="bottom", width bound to trigger via CSS var)
 * - cmdk Command primitive for filtering + keyboard nav
 * - Task-6 focus model (.hf-ink-focus) on the field wrapper
 * - @/lib/cn for class merging
 * - lucide-react LeafIcon as the row icon
 */
import * as React from "react";
import { LeafIcon, SearchIcon } from "lucide-react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { Command as CommandPrimitive } from "cmdk";

import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface ActionSearchItem {
  /** Unique identifier for the item. */
  id: string;
  /** The scientific binomial name (e.g. "Curcuma longa"). */
  binomial: string;
  /** Taxonomic family (e.g. "Zingiberaceae"). */
  family: string;
  /** Numeric count to display (compounds for plants, targets for diseases). */
  count: number;
  /** Label for the count (e.g. "compounds" or "targets"). */
  countLabel?: string;
}

export interface ActionSearchBarProps {
  /** The list of items to search through. */
  items: ActionSearchItem[];
  /** Placeholder text for the search field. */
  placeholder?: string;
  /** Called when the user selects an item. */
  onSelect: (item: ActionSearchItem) => void;
  /** Debounce delay in milliseconds before filtering. Default: 200 ms. */
  debounceMs?: number;
  /** Control the open state externally. */
  open?: boolean;
  /** Whether the popup is open by default (uncontrolled). */
  defaultOpen?: boolean;
  /** Called when the open state changes. */
  onOpenChange?: (open: boolean) => void;
  /** Additional class names for the root wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Debounce hook
// ---------------------------------------------------------------------------

function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState<T>(value);

  React.useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);

  return debounced;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function ActionSearchBar({
  items,
  placeholder = "Search...",
  onSelect,
  debounceMs = 200,
  open: openProp,
  defaultOpen = false,
  onOpenChange,
  className,
}: ActionSearchBarProps) {
  // Controlled/uncontrolled open state
  const [openState, setOpenState] = React.useState(defaultOpen);
  const isControlled = openProp !== undefined;
  const isOpen = isControlled ? openProp : openState;

  function handleOpenChange(next: boolean) {
    if (!isControlled) setOpenState(next);
    onOpenChange?.(next);
  }

  // Raw query typed by the user
  const [rawQuery, setRawQuery] = React.useState("");
  // Debounced query used for filtering
  const query = useDebounce(rawQuery, debounceMs);

  // Filter items against the debounced query
  const filtered = React.useMemo(() => {
    if (!query.trim()) return items;
    const q = query.toLowerCase();
    return items.filter(
      (item) => item.binomial.toLowerCase().includes(q) || item.family.toLowerCase().includes(q),
    );
  }, [items, query]);

  function handleSelect(item: ActionSearchItem) {
    onSelect(item);
    handleOpenChange(false);
    setRawQuery("");
  }

  return (
    <div className={cn("relative w-full", className)}>
      {/* Radix Popover handles the open/close + positioning */}
      <PopoverPrimitive.Root open={isOpen} onOpenChange={handleOpenChange}>
        {/* Trigger: the search field itself */}
        <PopoverPrimitive.Trigger asChild>
          {/*
           * The field wrapper carries:
           * - hf-ink-focus (Task-6 animated ink-border focus model)
           * - bg-hf-surface + border-hf-border-strong (solid form control)
           * - rounded-md (softened radius from spec §3)
           * data-slot lets tests target it
           */}
          <div
            data-slot="action-search-field"
            className={cn(
              "flex h-11 w-full items-center gap-2.5",
              "bg-hf-surface border-hf-border-strong rounded-md border",
              "px-3.5",
              "cursor-text",
              "hf-ink-focus",
            )}
            onClick={() => handleOpenChange(true)}
          >
            <SearchIcon aria-hidden className="text-hf-fg-3 h-4 w-4 shrink-0" />
            {/*
             * The input carries the combobox role and aria-expanded so that:
             * - getByRole("combobox") finds it directly
             * - fireEvent.change(input, ...) works (input has a value setter)
             * - aria-expanded reflects the open/closed state for a11y
             */}
            <input
              type="text"
              role="combobox"
              aria-expanded={isOpen}
              aria-haspopup="listbox"
              aria-autocomplete="list"
              aria-label={placeholder}
              placeholder={placeholder}
              value={rawQuery}
              onChange={(e) => {
                setRawQuery(e.target.value);
                if (!isOpen) handleOpenChange(true);
              }}
              onFocus={() => handleOpenChange(true)}
              className={cn(
                "text-hf-fg-1 placeholder:text-hf-fg-4",
                "h-full w-full min-w-0 bg-transparent",
                "text-sm outline-none",
              )}
            />
          </div>
        </PopoverPrimitive.Trigger>

        {/* Portal: popup opens downward, width = field width */}
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Content
            data-slot="action-search-popup"
            side="bottom"
            align="start"
            sideOffset={6}
            onOpenAutoFocus={(e) => e.preventDefault()}
            className={cn(
              // Width matches the trigger — Radix injects --radix-popover-trigger-width
              "w-[var(--radix-popover-trigger-width)]",
              // Surface + border + shadow
              "bg-hf-surface border-hf-border rounded-md border",
              "shadow-[var(--shadow-2)]",
              // Stacking
              "z-50 overflow-hidden",
              // Radix entrance animations (bottom placement → slide-in-from-top)
              "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
              "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
              "data-[side=bottom]:slide-in-from-top-2",
              "origin-[--radix-popover-content-transform-origin]",
            )}
          >
            {/* cmdk Command for keyboard navigation + a11y */}
            <CommandPrimitive shouldFilter={false} className="flex w-full flex-col">
              <CommandPrimitive.List
                role="listbox"
                aria-label="Search results"
                className="max-h-72 scroll-py-1 overflow-y-auto"
              >
                {filtered.length === 0 && (
                  <CommandPrimitive.Empty className="text-hf-fg-3 py-6 text-center text-sm">
                    No results found.
                  </CommandPrimitive.Empty>
                )}
                {filtered.map((item) => (
                  <ActionRowItem key={item.id} item={item} onSelect={handleSelect} />
                ))}
              </CommandPrimitive.List>
            </CommandPrimitive>
          </PopoverPrimitive.Content>
        </PopoverPrimitive.Portal>
      </PopoverPrimitive.Root>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rich result row
// ---------------------------------------------------------------------------

interface ActionRowItemProps {
  item: ActionSearchItem;
  onSelect: (item: ActionSearchItem) => void;
}

function ActionRowItem({ item, onSelect }: ActionRowItemProps) {
  return (
    <CommandPrimitive.Item
      data-slot="action-row"
      value={item.binomial}
      onSelect={() => onSelect(item)}
      className={cn(
        // Layout
        "flex items-center gap-3 px-3.5 py-2.5",
        // Surface + interaction
        "cursor-pointer select-none",
        "data-[selected=true]:bg-hf-surface-2",
        // Separator between rows
        "border-hf-border border-b last:border-b-0",
        // Transition
        "transition-colors duration-100",
      )}
    >
      {/* Leading icon: soft sage-tinted circle with a leaf */}
      <span
        data-slot="action-row-icon"
        aria-hidden
        className={cn(
          "inline-flex h-7 w-7 shrink-0 items-center justify-center",
          "rounded-lg",
          "bg-hf-sage-soft text-hf-sage-deep",
        )}
      >
        <LeafIcon className="h-3.5 w-3.5" aria-hidden />
      </span>

      {/* Name + family block */}
      <div className="min-w-0 flex-1">
        {/* Binomial: italic serif (Instrument Serif via .hf-binomial) */}
        <div
          data-slot="action-row-binomial"
          className="hf-binomial text-hf-fg-1 truncate text-sm leading-snug"
        >
          {item.binomial}
        </div>
        {/* Family: secondary muted text */}
        <div className="text-hf-fg-3 truncate text-xs leading-tight">{item.family}</div>
      </div>

      {/* Right-aligned count in mono */}
      <span
        data-slot="action-row-count"
        className="text-hf-fg-3 ml-auto shrink-0 font-mono text-xs tabular-nums"
      >
        {item.count.toLocaleString("en-US")}
        {item.countLabel ? <span className="text-hf-fg-4 ml-1">{item.countLabel}</span> : null}
      </span>
    </CommandPrimitive.Item>
  );
}

export { ActionSearchBar };
