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
            <span className="bg-accent text-accent-foreground inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium">
              {label}
              <button
                type="button"
                aria-label={`Remove ${label}`}
                onClick={() => onRemove(item)}
                className="hover:text-foreground ml-0.5 rounded-full opacity-60 transition-opacity hover:opacity-100"
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
