import { Link } from "@tanstack/react-router";
import type { AnalysisRead } from "@/api/types.gen";
import { StepperRail } from "@/components/ui/StepperRail";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { ExitRunDialog } from "@/components/stages/ExitRunDialog";

export function RunSidebar({
  data,
  analysisId,
  onExit,
}: {
  data: AnalysisRead;
  analysisId: string;
  onExit: () => void;
}) {
  return (
    <aside className="border-hf-border bg-hf-bg flex flex-col gap-4 border-b p-4 lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:w-64 lg:border-r lg:border-b-0">
      <Link to="/" className="font-display text-hf-fg-1 text-lg tracking-tight">
        Herbaflow
      </Link>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <StepperRail data={data} />
      </div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <div className="flex-1">
          <ExitRunDialog analysisId={analysisId} onExited={onExit} />
        </div>
      </div>
    </aside>
  );
}
