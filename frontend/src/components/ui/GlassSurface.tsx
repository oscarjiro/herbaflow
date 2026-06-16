import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export function GlassSurface({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "border-hf-border rounded-[var(--radius-1)] border bg-[var(--hf-glass-bg)]",
        "backdrop-blur-md motion-reduce:backdrop-blur-none",
        className,
      )}
    >
      {children}
    </div>
  );
}
