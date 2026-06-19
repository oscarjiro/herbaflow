import { useEffect, useState } from "react";
import { CheckIcon, ChevronsUpDownIcon, XIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { Button } from "./ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "./ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { useDebouncedValue } from "../hooks/useDebouncedValue";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ComboOption = {
  value: string;
  label: string;
  hint?: string | null;
};

type Props = {
  mode: "single" | "multiple";
  selected: ComboOption[];
  onChange: (next: ComboOption[]) => void;
  search: (q: string) => Promise<ComboOption[]>;
  max?: number;
  placeholder?: string;
  ariaLabel: string;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EntitySearchCombobox({
  mode,
  selected,
  onChange,
  search,
  max,
  placeholder = "Search…",
  ariaLabel,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ComboOption[]>([]);
  const [loading, setLoading] = useState(false);

  const debouncedQuery = useDebouncedValue(query, 300);

  // Fire search only while the popover is open and the debounced query settles, so a
  // pre-rendered combobox does not hit the server on mount before the user opens it.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    search(debouncedQuery)
      .then((rows) => {
        if (!cancelled) setResults(rows);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, debouncedQuery, search]);

  const atCap = mode === "multiple" && max !== undefined && selected.length >= max;

  function isSelected(value: string) {
    return selected.some((o) => o.value === value);
  }

  function toggle(opt: ComboOption) {
    if (mode === "single") {
      onChange([opt]);
      setOpen(false);
      return;
    }
    // multiple
    if (isSelected(opt.value)) {
      onChange(selected.filter((o) => o.value !== opt.value));
    } else {
      if (atCap) return; // blocked at cap
      onChange([...selected, opt]);
    }
  }

  function remove(value: string) {
    onChange(selected.filter((o) => o.value !== value));
  }

  // Trigger label
  let triggerLabel: string;
  if (mode === "single") {
    triggerLabel = selected[0]?.label ?? placeholder;
  } else {
    triggerLabel = selected.length > 0 ? `${selected.length} selected` : placeholder;
  }

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            aria-label={ariaLabel}
            className="w-full justify-between font-normal"
          >
            <span className={cn(!selected.length && "text-muted-foreground")}>{triggerLabel}</span>
            <ChevronsUpDownIcon className="ml-2 size-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>

        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput placeholder="Search…" value={query} onValueChange={setQuery} />
            <CommandList>
              {loading && (
                <CommandGroup>
                  <CommandItem disabled>Searching…</CommandItem>
                </CommandGroup>
              )}
              {!loading && results.length === 0 && <CommandEmpty>No matches.</CommandEmpty>}
              {!loading && results.length > 0 && (
                <CommandGroup>
                  {results.map((opt) => {
                    const selected_ = isSelected(opt.value);
                    const disabled = !selected_ && atCap;
                    return (
                      <CommandItem
                        key={opt.value}
                        value={opt.value}
                        disabled={disabled}
                        onSelect={() => toggle(opt)}
                        className="flex flex-col items-start gap-0"
                      >
                        <span className="flex w-full items-center gap-2">
                          <CheckIcon
                            className={cn(
                              "size-4 shrink-0",
                              selected_ ? "opacity-100" : "opacity-0",
                            )}
                          />
                          <span>{opt.label}</span>
                        </span>
                        {opt.hint && (
                          <span className="text-muted-foreground pl-6 text-xs">
                            matched: {opt.hint}
                          </span>
                        )}
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Selected chips */}
      {selected.length > 0 && (
        <ul aria-label={`Selected ${ariaLabel}`} className="flex flex-wrap gap-1.5">
          {selected.map((opt) => (
            <li key={opt.value}>
              <span className="bg-accent text-accent-foreground inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium">
                {opt.label}
                <button
                  type="button"
                  aria-label={`Remove ${opt.label}`}
                  onClick={() => remove(opt.value)}
                  className="hover:text-foreground ml-0.5 rounded-full opacity-60 transition-opacity hover:opacity-100"
                >
                  <XIcon className="size-3" />
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
