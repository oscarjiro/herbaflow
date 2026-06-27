import { type ReactNode, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { deleteAnalysis } from "@/api/sdk.gen";
import { clearActiveRunId } from "@/lib/activeRun";
import { notifyError } from "@/lib/toast";
import type { Problem } from "@/lib/problem";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function ExitRunDialog({
  analysisId,
  onExited,
  trigger,
}: {
  analysisId: string;
  onExited: () => void;
  /** Optional custom trigger element rendered via DialogTrigger asChild.
   * When omitted the default "Exit analysis" outline button is used. */
  trigger?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const del = useMutation({
    mutationFn: async () =>
      deleteAnalysis({ path: { analysis_id: analysisId }, throwOnError: true }),
    onSuccess: () => {
      clearActiveRunId();
      toast.success("Analysis deleted");
      setOpen(false);
      onExited();
    },
    onError: (error) => notifyError(error as Problem),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="secondary" size="sm" className="w-full">
            Exit analysis
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Exit this analysis?</DialogTitle>
          <DialogDescription>
            This run will be permanently deleted. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button variant="danger" disabled={del.isPending} onClick={() => del.mutate()}>
            {del.isPending ? "Deleting…" : "Delete and exit"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
