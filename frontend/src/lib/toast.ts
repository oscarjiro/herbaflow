import { toast } from "sonner";
import { humanizeProblem, type Problem } from "./problem";

export function notifyError(problem?: Problem | null): void {
  toast.error(humanizeProblem(problem));
}

export function notifySuccess(message: string): void {
  toast.success(message);
}

export function notifyInfo(message: string): void {
  toast.info(message);
}
