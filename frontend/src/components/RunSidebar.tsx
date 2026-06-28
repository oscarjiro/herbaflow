import { Link, useRouterState } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";
import type { AnalysisRead } from "@/api/types.gen";
import { Button } from "@/components/ui/button";
import { StepperRail } from "@/components/ui/StepperRail";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { ExitRunDialog } from "@/components/stages/ExitRunDialog";
import { RunIdentityCard } from "@/components/RunIdentityCard";
import { isValidStageSlug, type StageSlug } from "@/lib/stageRoutes";

// Active stage = the trailing slug of /analysis/{id}/{stage}, read from router-state location.
function useActiveStage(): StageSlug | undefined {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const segments = pathname.split("/").filter(Boolean);
  const candidate = segments[0] === "analysis" && segments.length >= 3 ? segments[2] : undefined;
  return candidate && isValidStageSlug(candidate) ? candidate : undefined;
}

// Glass danger trigger (UX-9: every button is glass). flex-1 fills the row beside
// the theme toggle; the foot-row's default align-items:stretch matches its height.
const cancelTrigger = (
  <Button variant="danger" size="sm" className="flex-1 justify-center">
    <Trash2 aria-hidden="true" className="size-[15px]" />
    Exit run
  </Button>
);

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
    <aside className="sidebar">
      {/* Brand */}
      <Link to="/" aria-label="Herbaflow home" className="brand">
        <span className="hf-logo block h-8 w-[132px]" aria-hidden="true" />
      </Link>

      {/* Run identity card */}
      <RunIdentityCard data={data} />

      {/* Scrollable stage trail */}
      <div
        className="scroll"
        style={{ flex: 1, minHeight: 0, overflowY: "auto", marginRight: "-4px" }}
      >
        <StepperRail data={data} analysisId={analysisId} activeSlug={activeSlug} />
      </div>

      {/* Sidebar footer: theme toggle + exit run */}
      <div className="side-foot">
        <div className="foot-row">
          <ThemeToggle />
          <ExitRunDialog analysisId={analysisId} onExited={onExit} trigger={cancelTrigger} />
        </div>
      </div>
    </aside>
  );
}
