import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export function Icon({ as: As, className }: { as: LucideIcon; className?: string }) {
  return <As strokeWidth={1.25} size={24} className={cn("shrink-0", className)} />;
}
