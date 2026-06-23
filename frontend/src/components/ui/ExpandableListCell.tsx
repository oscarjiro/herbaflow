import * as React from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// ExpandableListCell — collapsed chip list with an expandable "more" toggle.
//
// Used in per-stage data tables where a single cell holds a long list of
// strings (e.g. S1 plant sources, S3/S5 compound sources, S8 genes-in-term).
// The component is purely presentational: no data fetching, no CSV logic.
// CSV export always serialises the full list — handled by the caller.
// ---------------------------------------------------------------------------

interface ExpandableListCellProps {
  /** The full list of string values to display. */
  items: string[];
  /**
   * How many chips to show in the collapsed state before the toggle appears.
   * @default 3
   */
  collapsedCount?: number;
  /**
   * Optional renderer for each chip's content. When omitted the raw string is
   * used. Use this to wrap values in links, badges, or other markup.
   */
  renderItem?: (value: string) => React.ReactNode;
}

function ExpandableListCell({ items, collapsedCount = 3, renderItem }: ExpandableListCellProps) {
  const [expanded, setExpanded] = React.useState(false);

  // Empty list — render a muted placeholder.
  if (items.length === 0) {
    return (
      <span data-slot="expandable-list-cell" className="text-hf-fg-4 text-xs" aria-label="empty">
        –
      </span>
    );
  }

  const needsToggle = items.length > collapsedCount;
  const visible = needsToggle && !expanded ? items.slice(0, collapsedCount) : items;
  const hiddenCount = items.length - collapsedCount;

  return (
    <span data-slot="expandable-list-cell" className="flex flex-wrap gap-1">
      {visible.map((value, index) => (
        <span
          key={index}
          className={cn(
            "inline-flex items-center rounded-full",
            "border-hf-border bg-hf-surface-2 border",
            "text-hf-fg-2 px-2 py-0.5 text-xs",
          )}
        >
          {renderItem ? renderItem(value) : value}
        </span>
      ))}

      {needsToggle && !expanded && (
        <button
          type="button"
          aria-expanded={false}
          onClick={() => setExpanded(true)}
          className={cn(
            "inline-flex items-center rounded-full",
            "border-hf-border bg-hf-surface-2 border",
            "text-hf-fg-3 px-2 py-0.5 text-xs",
            "cursor-pointer transition-colors duration-[var(--duration-1)]",
            "hover:text-hf-fg-1 hover:bg-hf-surface-3",
            "focus-visible:outline-hf-fg-1 focus-visible:outline-[1.5px] focus-visible:outline-offset-1",
          )}
        >
          +{hiddenCount} more
        </button>
      )}

      {needsToggle && expanded && (
        <button
          type="button"
          aria-expanded={true}
          onClick={() => setExpanded(false)}
          className={cn(
            "inline-flex items-center rounded-full",
            "border-hf-border bg-hf-surface-2 border",
            "text-hf-fg-3 px-2 py-0.5 text-xs",
            "cursor-pointer transition-colors duration-[var(--duration-1)]",
            "hover:text-hf-fg-1 hover:bg-hf-surface-3",
            "focus-visible:outline-hf-fg-1 focus-visible:outline-[1.5px] focus-visible:outline-offset-1",
          )}
        >
          Show less
        </button>
      )}
    </span>
  );
}

export { ExpandableListCell };
export type { ExpandableListCellProps };
