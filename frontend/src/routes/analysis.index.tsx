import { createFileRoute } from "@tanstack/react-router";
import { AnalysisGate } from "@/components/AnalysisGate";
import { pageTitle, useDocumentTitle } from "@/lib/pageMeta";

export const Route = createFileRoute("/analysis/")({
  component: AnalysisSetupRoute,
});

function AnalysisSetupRoute() {
  useDocumentTitle(pageTitle(["New analysis"]));
  return <AnalysisGate />;
}
