import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { StatNumber } from "@/components/ui/editorial";
import { GlassSurface } from "@/components/ui/GlassSurface";
import { ColumnInfo } from "@/components/ui/ColumnInfo";

type StageSummaryCardProps = {
  label: string;
  value: ReactNode;
  ariaLabel: string;
  muted?: boolean;
  /** Plain-language definition shown via the same circle-i affordance as the data-table
   *  column headers. Reuses ColumnInfo so there is one tooltip primitive across the app. */
  info?: string;
  /** Override the value type size (default text-2xl). Use for long text values
   *  like the Stage-8 correction name so they don't dwarf the card. */
  valueClassName?: string;
};

export function StageSummaryCard({
  label,
  value,
  ariaLabel,
  muted,
  info,
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
        <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
          {label}
          {info ? <ColumnInfo text={info} label={`About ${label}`} /> : null}
        </span>
      </div>
    </GlassSurface>
  );
}
