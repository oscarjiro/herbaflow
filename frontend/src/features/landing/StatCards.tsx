import { Leaf, Hexagon, HeartPulse } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

// Live-DB entity counts as of the last data reload.
const STATS = [
  {
    icon: Leaf,
    num: "478",
    label: "Indonesian medicinal plants",
    sub: "Ethnobotanically used, literature-curated",
  },
  {
    icon: Hexagon,
    num: "11,307",
    label: "Bioactive compounds",
    sub: "Plant metabolites from KNApSAcK",
  },
  {
    icon: HeartPulse,
    num: "10",
    label: "Curated diseases",
    sub: "Well-studied and clinically relevant",
  },
] as const;

export function StatCards({ className }: { className?: string }) {
  return (
    <div
      className={cn("grid grid-cols-1 gap-4 sm:grid-cols-3", className)}
      data-testid="stat-cards"
    >
      {STATS.map(({ icon: Icon, num, label, sub }) => (
        <Card key={label} variant="glass-raised" className="p-5">
          <div className="grid grid-cols-[52px_1fr] items-center gap-4">
            <div className="bg-hf-surface text-hf-fg-1 border-hf-border grid size-[52px] shrink-0 place-items-center rounded-[var(--radius-md)] border">
              <Icon size={22} strokeWidth={1.25} aria-hidden="true" />
            </div>
            <div>
              <div className="font-display text-hf-fg-1 text-[clamp(2.1rem,3.4vw,2.7rem)] leading-none tracking-tight">
                {num}
              </div>
              <div className="font-display text-hf-fg-1 mt-0.5 text-[19px]">{label}</div>
              <div className="text-hf-fg-3 mt-1 text-xs">{sub}</div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
