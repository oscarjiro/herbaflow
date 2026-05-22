import * as React from "react";
import { Check, ChevronsUpDown, X } from "lucide-react";

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
    const { data: plants = [], isLoading } = usePlants();

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
                    <Command>
                        <CommandInput placeholder="Search plants..." />
                        <CommandList className="max-h-64">
                            {isLoading && (
                                <CommandEmpty>Loading plants...</CommandEmpty>
                            )}
                            {!isLoading && plants.length === 0 && (
                                <CommandEmpty>No plants found.</CommandEmpty>
                            )}
                            {!isLoading && plants.length > 0 && (
                                <CommandGroup>
                                    {plants.map((plant) => {
                                        const selected = value.includes(
                                            plant.plant_id,
                                        );
                                        return (
                                            <CommandItem
                                                key={plant.plant_id}
                                                value={`${plant.canonical_scientific_name} ${plant.family_name ?? ""}`}
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
