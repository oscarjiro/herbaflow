import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { StatNumber } from "@/components/ui/editorial";
import { GlassSurface } from "@/components/ui/GlassSurface";

type StageSummaryCardProps = {
  label: string;
  value: ReactNode;
  ariaLabel: string;
  muted?: boolean;
  /** Override the value type size (default text-2xl). Use for long text values
   *  like the Stage-8 correction name so they don't dwarf the card. */
  valueClassName?: string;
};

export function StageSummaryCard({
  label,
  value,
  ariaLabel,
  muted,
  valueClassName,
}: StageSummaryCardProps) {
  return (
    <GlassSurface tier="raised" className="min-w-[96px] rounded-lg" aria-label={ariaLabel}>
      <div className="flex flex-col items-center px-4 py-3">
        <StatNumber
          className={cn(
            "font-display text-2xl font-semibold",
            muted && "text-muted-foreground",
            valueClassName,
          )}
        >
          {value}
        </StatNumber>
        <span className="text-muted-foreground text-xs">{label}</span>
      </div>
    </GlassSurface>
  );
}
