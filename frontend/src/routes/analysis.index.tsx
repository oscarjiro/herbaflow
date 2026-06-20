import { createFileRoute } from "@tanstack/react-router";
import { AnalysisGate } from "@/components/AnalysisGate";

export const Route = createFileRoute("/analysis/")({
  component: AnalysisGate,
});
