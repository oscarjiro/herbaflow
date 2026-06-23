import { useEffect, useState } from "react";
import { SearchIcon, XIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "./ui/command";
import { Popover, PopoverAnchor, PopoverContent } from "./ui/popover";
import { useDebouncedValue } from "../hooks/useDebouncedValue";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ComboOption = {
  value: string;
  label: string;
  hint?: string | null;
  familyName?: string | null;
  count?: number;
  kind?: "plant" | "disease";
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
// Plant leaf SVG glyph (used in .sres and .sel-card for plants)
// ---------------------------------------------------------------------------

function PlantGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M11 20A7 7 0 0 1 4 13c0-4 3-7 7-9 0 0-1 4 1 6M11 20c0-4 2-8 6-10 0 0 1 5-2 8a6 6 0 0 1-4 2z" />
    </svg>
  );
}

function DiseaseGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Rich result row (.sres)
// ---------------------------------------------------------------------------

function SresRow({ opt }: { opt: ComboOption }) {
  const isPlant = opt.kind === "plant";
  const countStr = opt.count !== undefined ? opt.count.toLocaleString() : null;
  const countLabel = countStr
    ? isPlant
      ? `${countStr} compounds`
      : `${countStr} disease targets`
    : null;

  return (
    <span className="flex w-full items-center gap-3">
      {/* Glyph tile */}
      <span className="bg-hf-sage-soft text-hf-sage-deep flex size-[30px] shrink-0 items-center justify-center rounded-[8px]">
        {isPlant ? <PlantGlyph className="size-4" /> : <DiseaseGlyph className="size-4" />}
      </span>

      {/* Name + family */}
      <span className="min-w-0 flex-1">
        <span className="block text-[14px] leading-snug">
          {isPlant ? (
            <span className="font-display italic">{opt.label}</span>
          ) : (
            <span className="font-sans font-normal">{opt.label}</span>
          )}
        </span>
        {isPlant && opt.familyName && (
          <span className="text-hf-fg-3 block text-[12px] leading-tight">{opt.familyName}</span>
        )}
        {opt.hint && (
          <span className="text-hf-fg-4 block text-[11px] leading-tight">matched: {opt.hint}</span>
        )}
      </span>

      {/* Count badge */}
      {countLabel && (
        <span className="text-hf-fg-3 ml-auto shrink-0 font-mono text-[12px]">{countLabel}</span>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Selected entity card (.sel-card)
// ---------------------------------------------------------------------------

function SelCardList({
  items,
  onRemove,
  ariaLabel,
}: {
  items: ComboOption[];
  onRemove: (value: string) => void;
  ariaLabel: string;
}) {
  if (items.length === 0) return null;

  return (
    <ul aria-label={ariaLabel} className="flex flex-col gap-2">
      {items.map((opt) => {
        const isPlant = opt.kind === "plant";
        const countStr = opt.count !== undefined ? opt.count.toLocaleString() : null;
        const metaParts: string[] = [];
        if (isPlant && opt.familyName) metaParts.push(opt.familyName);
        const countSuffix = countStr
          ? isPlant
            ? `${countStr} compounds`
            : `${countStr} disease targets`
          : null;

        return (
          <li key={opt.value}>
            <div className="bg-hf-bg border-hf-border flex items-center gap-[11px] rounded-[var(--radius-md)] border px-[11px] py-[9px]">
              {/* Glyph circle */}
              <span className="bg-hf-sage-soft text-hf-fg-1 flex size-[30px] shrink-0 items-center justify-center rounded-full">
                {isPlant ? <PlantGlyph className="size-4" /> : <DiseaseGlyph className="size-4" />}
              </span>

              {/* Body */}
              <div className="min-w-0 flex-1">
                {isPlant ? (
                  <div className="font-display text-hf-fg-1 text-[1.06rem] leading-[1.15] italic">
                    {opt.label}
                  </div>
                ) : (
                  <div className="text-hf-fg-1 font-sans text-[0.98rem] leading-[1.15] font-semibold">
                    {opt.label}
                  </div>
                )}
                {(metaParts.length > 0 || countSuffix) && (
                  <div className="text-hf-fg-3 mt-[1px] text-[0.74rem]">
                    {metaParts.length > 0 && <span>{metaParts.join(" · ")}</span>}
                    {metaParts.length > 0 && countSuffix && <span> · </span>}
                    {countSuffix && <span className="text-hf-fg-2 font-mono">{countSuffix}</span>}
                  </div>
                )}
              </div>

              {/* Remove button */}
              <button
                type="button"
                aria-label={`Remove ${opt.label}`}
                onClick={() => onRemove(opt.value)}
                className="text-hf-fg-4 hover:text-hf-terracotta hover:bg-hf-surface-2 grid size-6 shrink-0 cursor-pointer place-items-center rounded-full border-0 bg-transparent transition-colors"
              >
                <XIcon className="size-3.5" aria-hidden="true" />
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

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
  const [focused, setFocused] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ComboOption[]>([]);
  const [loading, setLoading] = useState(false);

  const debouncedQuery = useDebouncedValue(query, 300);

  // Fire search only while the input is focused and the debounced query settles,
  // so a pre-rendered combobox does not hit the server on mount before the user types.
  useEffect(() => {
    if (!focused) return;
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
  }, [focused, debouncedQuery, search]);

  const atCap = mode === "multiple" && max !== undefined && selected.length >= max;

  function isSelected(value: string) {
    return selected.some((o) => o.value === value);
  }

  function toggle(opt: ComboOption) {
    if (mode === "single") {
      onChange([opt]);
      setQuery("");
      setFocused(false);
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

  // Dropdown appears only while the input is focused AND the user has typed something.
  const dropdownOpen = focused && query.trim().length > 0;

  return (
    <div className="space-y-2">
      <Popover
        open={dropdownOpen}
        onOpenChange={(o) => {
          if (!o) setFocused(false);
        }}
      >
        <PopoverAnchor asChild>
          <div className="relative">
            <SearchIcon
              className="text-hf-fg-4 pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
              aria-hidden="true"
            />
            <input
              type="text"
              role="combobox"
              aria-expanded={dropdownOpen}
              aria-label={ariaLabel}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setFocused(true)}
              placeholder={placeholder}
              className="border-hf-border-strong text-hf-fg-1 placeholder:text-hf-fg-4 bg-hf-bg focus:border-hf-fg-1 w-full rounded-[11px] border py-[11px] pr-[14px] pl-9 font-sans text-[0.88rem] outline-none focus:shadow-[0_2px_12px_-2px_var(--hf-sage)]"
            />
          </div>
        </PopoverAnchor>

        <PopoverContent
          className="bg-hf-surface w-[var(--radix-popover-trigger-width)] overflow-hidden rounded-[11px] border-[var(--hf-border)] p-0 shadow-md"
          align="start"
          sideOffset={6}
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <Command shouldFilter={false}>
            <CommandList className="scroll max-h-72">
              {loading && (
                <CommandGroup>
                  <CommandItem disabled>Searching…</CommandItem>
                </CommandGroup>
              )}
              {!loading && results.length === 0 && <CommandEmpty>No matches.</CommandEmpty>}
              {!loading && results.length > 0 && (
                <CommandGroup className="p-0">
                  {results.map((opt) => {
                    const sel = isSelected(opt.value);
                    const disabled = !sel && atCap;
                    return (
                      <CommandItem
                        key={opt.value}
                        value={opt.value}
                        disabled={disabled}
                        onSelect={() => toggle(opt)}
                        className={cn(
                          "hover:bg-hf-surface-2 rounded-none border-b border-[var(--hf-border)] px-0 py-0 last:border-b-0",
                          sel && "bg-hf-surface-2",
                        )}
                      >
                        <div className="flex w-full items-center gap-3 px-[14px] py-[11px]">
                          <SresRow opt={opt} />
                        </div>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Selected entity cards (.sel-card) */}
      <SelCardList items={selected} onRemove={remove} ariaLabel={`Selected ${ariaLabel}`} />
    </div>
  );
}
