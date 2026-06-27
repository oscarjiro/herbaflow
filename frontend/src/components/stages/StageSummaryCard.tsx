import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { StatNumber } from "@/components/ui/editorial";

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
    <div
      className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
      aria-label={ariaLabel}
    >
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
  );
}
