import { XIcon } from "lucide-react";

export function RemovableChipList<T>({
  items,
  getKey,
  getLabel,
  onRemove,
  ariaLabel,
}: {
  items: T[];
  getKey: (item: T) => string;
  getLabel: (item: T) => string;
  onRemove: (item: T) => void;
  ariaLabel: string;
}) {
  if (items.length === 0) return null;
  return (
    <ul aria-label={ariaLabel} className="flex flex-wrap gap-1.5">
      {items.map((item) => {
        const label = getLabel(item);
        return (
          <li key={getKey(item)}>
            <span className="bg-hf-bg border-hf-border-strong text-hf-fg-1 inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border py-1 pr-1.5 pl-3 font-mono text-xs">
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
    </ul>
  );
}
