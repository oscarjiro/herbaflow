import { Link, useParams } from "@tanstack/react-router";
import type { AnalysisRead } from "@/api/types.gen";
import { StepperRail } from "@/components/ui/StepperRail";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { ExitRunDialog } from "@/components/stages/ExitRunDialog";
import { RunIdentityCard } from "@/components/RunIdentityCard";
import { GlassSurface } from "@/components/ui/GlassSurface";
import type { StageSlug } from "@/lib/stageRoutes";

function useActiveStage(): StageSlug | undefined {
  try {
    const params = useParams({ strict: false }) as { stage?: StageSlug };
    return params.stage;
  } catch {
    return undefined;
  }
}

export function RunSidebar({
  data,
  analysisId,
  onExit,
}: {
  data: AnalysisRead;
  analysisId: string;
  onExit: () => void;
}) {
  const activeSlug = useActiveStage();
  return (
    <GlassSurface
      tier="chrome"
      className="flex flex-col gap-4 rounded-none border-0 p-4 lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:w-64 lg:border-r"
    >
      <Link to="/" className="font-display text-hf-fg-1 text-lg tracking-tight">
        Herbaflow
      </Link>
      <RunIdentityCard data={data} />
      <div className="scroll min-h-0 flex-1 overflow-y-auto">
        <StepperRail data={data} analysisId={analysisId} activeSlug={activeSlug} />
      </div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <div className="flex-1">
          <ExitRunDialog analysisId={analysisId} onExited={onExit} />
        </div>
      </div>
    </GlassSurface>
  );
}
