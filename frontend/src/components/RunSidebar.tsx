import { Link, useRouterState } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";
import type { AnalysisRead } from "@/api/types.gen";
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

const cancelTrigger = (
  <button type="button" className="icon-btn danger" style={{ flex: 1 }}>
    <Trash2 aria-hidden="true" style={{ width: 15, height: 15 }} />
    Cancel run
  </button>
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
        <span className="mark">Herbaflow</span>
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

      {/* Sidebar footer: theme toggle + cancel run */}
      <div className="side-foot">
        <div className="foot-row">
          <ThemeToggle />
          <ExitRunDialog analysisId={analysisId} onExited={onExit} trigger={cancelTrigger} />
        </div>
      </div>
    </aside>
  );
}
