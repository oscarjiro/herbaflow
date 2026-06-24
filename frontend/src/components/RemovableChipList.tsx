import { useState } from "react";
import { XIcon } from "lucide-react";
import type { ResolvedCompound, ResolvedTarget } from "@/api/types.gen";
import { EntryOverflowDialog } from "@/components/stages/EntryOverflowDialog";

// ---------------------------------------------------------------------------
// RemovableChipList
//
// Renders a cloud of removable chips for added compounds or targets.
//
// When `overflowKind` is provided and the item count exceeds CHIP_DISPLAY_LIMIT,
// it collapses to show the first CHIP_DISPLAY_LIMIT chips and a "+N more" button
// that opens EntryOverflowDialog with the full filterable/sortable list.
// ---------------------------------------------------------------------------

const CHIP_DISPLAY_LIMIT = 10;

// ---------------------------------------------------------------------------
// Core generic chip list — used for any T.
// Does NOT support overflow (no dialog can be opened without a typed kind).
// ---------------------------------------------------------------------------

function ChipList<T>({
  items,
  visibleItems,
  getKey,
  getLabel,
  onRemove,
  ariaLabel,
  onShowMore,
  hiddenCount,
  totalCount,
}: {
  items: T[];
  visibleItems: T[];
  getKey: (item: T) => string;
  getLabel: (item: T) => string;
  onRemove: (item: T) => void;
  ariaLabel: string;
  onShowMore?: () => void;
  hiddenCount: number;
  totalCount: number;
}) {
  if (items.length === 0) return null;

  return (
    <ul
      aria-label={ariaLabel}
      className="bg-hf-sage-faint border-hf-sage dark:border-hf-border-strong flex flex-wrap gap-1.5 rounded-[var(--radius-md)] border p-2 shadow-[0_10px_24px_-20px_var(--hf-sage-deep),inset_0_1px_0_rgba(255,255,255,0.7)] dark:bg-transparent dark:shadow-none"
    >
      {visibleItems.map((item) => {
        const label = getLabel(item);
        return (
          <li key={getKey(item)}>
            <span className="bg-hf-surface border-hf-sage text-hf-fg-1 dark:border-hf-border-strong inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border py-1 pr-1.5 pl-3 font-mono text-xs shadow-[0_1px_2px_rgba(26,26,26,0.08)]">
              {label}
              <button
                type="button"
                aria-label={`Remove ${label}`}
                onClick={() => onRemove(item)}
                className="text-hf-fg-4 hover:text-hf-terracotta grid size-4 place-items-center rounded-full transition-colors"
              >
                <XIcon className="size-3" />
              </button>
            </span>
          </li>
        );
      })}

      {hiddenCount > 0 && onShowMore && (
        <li>
          <button
            type="button"
            aria-label={`Show all ${totalCount} items`}
            onClick={onShowMore}
            className="bg-hf-surface border-hf-sage text-hf-fg-3 hover:text-hf-fg-1 hover:border-hf-sage-deep dark:border-hf-border-strong dark:hover:border-hf-border inline-flex items-center rounded-[var(--radius-pill)] border px-3 py-1 font-mono text-xs transition-colors"
          >
            +{hiddenCount} more
          </button>
        </li>
      )}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Public prop shapes
// ---------------------------------------------------------------------------

interface GenericProps<T> {
  items: T[];
  getKey: (item: T) => string;
  getLabel: (item: T) => string;
  onRemove: (item: T) => void;
  ariaLabel: string;
  overflowKind?: never;
}

interface CompoundProps {
  items: ResolvedCompound[];
  getKey: (item: ResolvedCompound) => string;
  getLabel: (item: ResolvedCompound) => string;
  onRemove: (item: ResolvedCompound) => void;
  ariaLabel: string;
  overflowKind: "compounds";
}

interface TargetProps {
  items: ResolvedTarget[];
  getKey: (item: ResolvedTarget) => string;
  getLabel: (item: ResolvedTarget) => string;
  onRemove: (item: ResolvedTarget) => void;
  ariaLabel: string;
  overflowKind: "targets";
}

// ---------------------------------------------------------------------------
// Main component — discriminates on overflowKind at render time.
// ---------------------------------------------------------------------------

// Overloaded call signatures so callers get precise prop types.
export function RemovableChipList(props: CompoundProps): React.ReactElement | null;
export function RemovableChipList(props: TargetProps): React.ReactElement | null;
export function RemovableChipList<T>(props: GenericProps<T>): React.ReactElement | null;
export function RemovableChipList<T>(
  props: CompoundProps | TargetProps | GenericProps<T>,
): React.ReactElement | null {
  const [dialogOpen, setDialogOpen] = useState(false);

  const { items, ariaLabel, overflowKind } = props;

  const hasOverflow = overflowKind !== undefined && items.length > CHIP_DISPLAY_LIMIT;
  const hiddenCount = hasOverflow ? items.length - CHIP_DISPLAY_LIMIT : 0;

  if (items.length === 0) return null;

  if (overflowKind === "compounds") {
    const compoundProps = props as CompoundProps;
    return (
      <>
        <ChipList
          items={compoundProps.items}
          visibleItems={compoundProps.items.slice(
            0,
            hasOverflow ? CHIP_DISPLAY_LIMIT : compoundProps.items.length,
          )}
          getKey={compoundProps.getKey}
          getLabel={compoundProps.getLabel}
          onRemove={compoundProps.onRemove}
          ariaLabel={ariaLabel}
          onShowMore={() => setDialogOpen(true)}
          hiddenCount={hiddenCount}
          totalCount={compoundProps.items.length}
        />
        <EntryOverflowDialog
          kind="compounds"
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          title={ariaLabel}
          items={compoundProps.items}
          onRemove={(id) => {
            const found = compoundProps.items.find((x) => x.compound_id === id);
            if (found) compoundProps.onRemove(found);
          }}
        />
      </>
    );
  }

  if (overflowKind === "targets") {
    const targetProps = props as TargetProps;
    return (
      <>
        <ChipList
          items={targetProps.items}
          visibleItems={targetProps.items.slice(
            0,
            hasOverflow ? CHIP_DISPLAY_LIMIT : targetProps.items.length,
          )}
          getKey={targetProps.getKey}
          getLabel={targetProps.getLabel}
          onRemove={targetProps.onRemove}
          ariaLabel={ariaLabel}
          onShowMore={() => setDialogOpen(true)}
          hiddenCount={hiddenCount}
          totalCount={targetProps.items.length}
        />
        <EntryOverflowDialog
          kind="targets"
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          title={ariaLabel}
          items={targetProps.items}
          onRemove={(id) => {
            const found = targetProps.items.find((x) => x.target_id === id);
            if (found) targetProps.onRemove(found);
          }}
        />
      </>
    );
  }

  // Generic (no overflow dialog)
  const genericProps = props as GenericProps<T>;
  return (
    <ChipList
      items={genericProps.items}
      visibleItems={genericProps.items}
      getKey={genericProps.getKey}
      getLabel={genericProps.getLabel}
      onRemove={genericProps.onRemove}
      ariaLabel={ariaLabel}
      hiddenCount={0}
      totalCount={genericProps.items.length}
    />
  );
}
