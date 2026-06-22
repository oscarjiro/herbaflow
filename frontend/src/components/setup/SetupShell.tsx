import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { GlassSurface } from "@/components/ui/GlassSurface";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { PreRunTrail } from "@/components/setup/PreRunTrail";

// Unified analysis shell for the pre-run (setup) state: the same glass chrome sidebar as the run
// page, with a static pre-run trail and the setup form in the content pane.
export function SetupShell({ children }: { children: ReactNode }) {
  return (
    <div className="lg:pl-64">
      <GlassSurface
        tier="chrome"
        className="flex flex-col gap-4 rounded-none border-0 p-4 lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:w-64 lg:border-r"
      >
        <Link to="/" className="font-display text-hf-fg-1 text-lg tracking-tight">
          Herbaflow
        </Link>
        <div className="scroll min-h-0 flex-1 overflow-y-auto">
          <PreRunTrail />
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
        </div>
      </GlassSurface>
      <main className="mx-auto min-w-0">{children}</main>
    </div>
  );
}
