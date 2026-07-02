import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { AnalysisRead } from "@/api/types.gen";
import { RunSidebarContent } from "@/components/RunSidebar";
import { HamburgerIcon } from "@/components/ui/HamburgerIcon";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { activeStageSlugFromPath, slugToStage, type StageSlug } from "@/lib/stageRoutes";
import { cn } from "@/lib/cn";

function runStatusLabel(status: string | null | undefined): string {
  if (status === "pending") return "Preparing";
  if (status === "complete") return "Complete";
  if (status === "failed") return "Needs attention";

  const phase = /^stage_\d+_(starting|running|awaiting_approval|complete)$/.exec(status ?? "")?.[1];
  if (phase === "starting") return "Starting";
  if (phase === "running") return "Running";
  if (phase === "awaiting_approval") return "Awaiting approval";
  if (phase === "complete") return "Stage complete";

  return "Status unavailable";
}

// Status-dot tone: red for a failed run, amber while awaiting approval, green on
// complete, calm ink for the in-flight states.
function statusTone(status: string | null | undefined): string {
  if (status === "failed") return "bg-hf-danger";
  if (status === "complete") return "bg-hf-success";
  if (/awaiting_approval$/.test(status ?? "")) return "bg-hf-warning";
  return "bg-hf-fg-1";
}

// "Step N" for the eight pipeline stages; a plain setup/results label for the
// inputs/final bookends (which are not numbered pipeline steps).
function stepLabel(activeSlug: StageSlug): string {
  const n = slugToStage(activeSlug);
  if (n != null) return `Step ${n}`;
  if (activeSlug === "final") return "Results";
  return "Setup";
}

export function RunMobileNavigation({
  data,
  analysisId,
  onExit,
  pathname,
}: {
  data: AnalysisRead;
  analysisId: string;
  onExit: () => void;
  pathname: string;
}) {
  const [open, setOpen] = useState(false);
  const activeSlug = (activeStageSlugFromPath(pathname) ?? "inputs") as StageSlug;

  return (
    <Drawer open={open} onOpenChange={setOpen}>
      {/* Translucent glass top bar: burger (left) · wordmark (centre) · step + status (right).
          The drawer opens from the left, so the burger sits on the left to match. */}
      <header className="border-hf-border bg-hf-bg/25 supports-[backdrop-filter]:bg-hf-bg/12 sticky top-0 z-30 border-b backdrop-blur-xl backdrop-saturate-150 lg:hidden">
        <div className="mx-auto flex max-w-[920px] items-center gap-2 px-4 py-3">
          <div className="flex flex-1 justify-start">
            <button
              type="button"
              aria-label="Open run navigation"
              onClick={() => setOpen(true)}
              className="hf-ink-focus text-hf-fg-1 -m-2 inline-flex items-center justify-center rounded-md p-2"
            >
              <HamburgerIcon open={open} />
            </button>
          </div>

          <Link to="/" aria-label="Herbaflow home" className="text-hf-fg-1 shrink-0">
            <span className="hf-logo block h-6 w-[112px]" aria-hidden="true" />
          </Link>

          {/* Step over status, two short right-aligned lines so both stay visible
              (and never overflow the logo off-centre) down to the 320px floor. */}
          <div className="flex flex-1 flex-col items-end leading-tight">
            <span className="text-hf-fg-3 font-mono text-[0.6rem] tracking-[0.14em] uppercase">
              {stepLabel(activeSlug)}
            </span>
            <span className="text-hf-fg-2 flex items-center gap-1.5 text-xs whitespace-nowrap">
              <span
                aria-hidden="true"
                className={cn("size-1.5 rounded-full", statusTone(data.status))}
              />
              {runStatusLabel(data.status)}
            </span>
          </div>
        </div>
      </header>

      <DrawerContent side="left" className="sidebar flex w-[min(22rem,calc(100vw-1rem))]">
        <DrawerHeader className="sr-only">
          <DrawerTitle>Run navigation</DrawerTitle>
          <DrawerDescription>Navigate between analysis steps.</DrawerDescription>
        </DrawerHeader>
        <RunSidebarContent
          data={data}
          analysisId={analysisId}
          onExit={onExit}
          onNavigate={() => setOpen(false)}
        />
      </DrawerContent>
    </Drawer>
  );
}
