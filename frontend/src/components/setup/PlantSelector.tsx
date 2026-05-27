import * as React from "react";
import { Check, ChevronsUpDown, X } from "lucide-react";
import Fuse from "fuse.js";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import { usePlants } from "@/hooks/usePlants";

interface PlantSelectorProps {
    value: string[];
    onChange: (ids: string[]) => void;
}

export function PlantSelector({ value, onChange }: PlantSelectorProps) {
    const [open, setOpen] = React.useState(false);
    const [query, setQuery] = React.useState("");
    const { data: plants = [], isLoading } = usePlants();

    // Reset query when popover closes
    React.useEffect(() => {
        if (!open) setQuery("");
    }, [open]);

    // Fuse instance — recreated only when the plants list changes
    const fuse = React.useMemo(
        () =>
            new Fuse(plants, {
                keys: [
                    { name: 'canonical_scientific_name', weight: 1.0 },
                    { name: 'family_name', weight: 0.5 },
                    { name: 'plant_aliases', weight: 0.6 },
                ],
                threshold: 0.4,
                includeScore: true,
            }),
        [plants],
    );

    // Fuzzy-filtered list — if no query, show all plants
    const filtered = React.useMemo(() => {
        if (!query.trim()) return plants;
        return fuse.search(query).map((r) => r.item);
    }, [fuse, query, plants]);

    function toggle(id: string) {
        if (value.includes(id)) {
            onChange(value.filter((v) => v !== id));
        } else {
            onChange([...value, id]);
        }
    }

    function remove(id: string) {
        onChange(value.filter((v) => v !== id));
    }

    const selectedPlants = plants.filter((p) => value.includes(p.plant_id));

    return (
        <div className="flex flex-col gap-2">
            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                    <Button
                        variant="outline"
                        role="combobox"
                        aria-expanded={open}
                        className="w-full justify-between bg-hf-surface border-hf-border text-hf-fg2 rounded-sm"
                    >
                        <span
                            className={
                                value.length === 0 ? "text-hf-fg3" : undefined
                            }
                        >
                            {value.length === 0
                                ? "Select plants..."
                                : `${value.length} plant${value.length === 1 ? "" : "s"} selected`}
                        </span>
                        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent
                    className="w-[var(--radix-popover-trigger-width)] p-0"
                    align="start"
                >
                    {/* shouldFilter={false}: fuse.js handles filtering, not cmdk */}
                    <Command shouldFilter={false}>
                        <CommandInput
                            placeholder="Search plants..."
                            value={query}
                            onValueChange={setQuery}
                        />
                        <CommandList className="max-h-64">
                            {isLoading && (
                                <CommandEmpty>Loading plants...</CommandEmpty>
                            )}
                            {!isLoading && filtered.length === 0 && (
                                <CommandEmpty>No plants found.</CommandEmpty>
                            )}
                            {!isLoading && filtered.length > 0 && (
                                <CommandGroup>
                                    {filtered.map((plant) => {
                                        const selected = value.includes(
                                            plant.plant_id,
                                        );
                                        return (
                                            <CommandItem
                                                key={plant.plant_id}
                                                value={plant.plant_id}
                                                onSelect={() =>
                                                    toggle(plant.plant_id)
                                                }
                                            >
                                                <Check
                                                    className={cn(
                                                        "mr-2 h-4 w-4 shrink-0",
                                                        selected
                                                            ? "opacity-100"
                                                            : "opacity-0",
                                                    )}
                                                />
                                                <div className="flex flex-1 items-center justify-between min-w-0">
                                                    <div className="flex flex-col min-w-0">
                                                        <span className="text-sm text-hf-fg1 truncate">
                                                            {
                                                                plant.canonical_scientific_name
                                                            }
                                                        </span>
                                                        {plant.family_name && (
                                                            <span className="text-xs text-hf-fg3 truncate">
                                                                {
                                                                    plant.family_name
                                                                }
                                                            </span>
                                                        )}
                                                    </div>
                                                    <Badge
                                                        variant="secondary"
                                                        className="ml-2 shrink-0 text-xs"
                                                    >
                                                        {plant.compound_count}
                                                    </Badge>
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

            {selectedPlants.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {selectedPlants.map((plant) => (
                        <span
                            key={plant.plant_id}
                            className="inline-flex items-center gap-1 rounded-sm bg-hf-sage-faint border border-hf-border px-2 py-0.5 text-xs text-hf-fg1"
                        >
                            <span className="italic">
                                {plant.canonical_scientific_name}
                            </span>
                            <button
                                type="button"
                                onClick={() => remove(plant.plant_id)}
                                className="text-hf-fg3 hover:text-hf-fg1 transition-colors"
                                aria-label={`Remove ${plant.canonical_scientific_name}`}
                            >
                                <X className="h-3 w-3" />
                            </button>
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
