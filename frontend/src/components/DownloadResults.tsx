import type { ElementType } from "react";
import { Download, FileText, FolderArchive, Network } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { fetchBlobDownload } from "../lib/download";
import type { Problem } from "../lib/problem";
import { notifyError, notifySuccess } from "../lib/toast";
import {
  exportAllResultsUrl,
  exportNetworkBundleUrl,
  exportReportUrl,
  exportStagesBundleUrl,
} from "../lib/exportUrl";
import { runHasCtp } from "../lib/entities";
import type { AnalysisRead } from "../api/types.gen";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Eyebrow } from "./ui/editorial";
import { Separator } from "./ui/separator";

type DownloadLink = {
  label: string;
  href: string;
  icon: ElementType;
  variant: "default" | "outline";
};

/** Download panel — shown only once the run is complete. Artifacts are fetched
 * via fetch-blob so success/error feedback surfaces as toasts. */
export function DownloadResults({
  status,
  analysisId,
  run,
}: {
  status: string | null | undefined;
  analysisId: string;
  run: AnalysisRead;
}) {
  if (status !== "complete") return null;

  // The Cytoscape network bundle holds compound-target-pathway edge tables; it requires
  // compounds, a non-empty Stage-5 overlap, and non-empty Stage-8 pathways. Without all
  // three the backend 404s that bundle, so only show it when runHasCtp is true. The PPI
  // network stays available via the stages and all-results bundles regardless.
  const links: DownloadLink[] = [
    {
      label: "Report (.md)",
      href: exportReportUrl(analysisId),
      icon: FileText,
      variant: "default",
    },
    ...(runHasCtp(run)
      ? ([
          {
            label: "Cytoscape network (.zip)",
            href: exportNetworkBundleUrl(analysisId),
            icon: Network,
            variant: "outline",
          },
        ] satisfies DownloadLink[])
      : []),
    {
      label: "All stages (.zip)",
      href: exportStagesBundleUrl(analysisId),
      icon: FolderArchive,
      variant: "outline",
    },
    {
      label: "All results (.zip)",
      href: exportAllResultsUrl(analysisId),
      icon: Download,
      variant: "outline",
    },
  ];

  return <DownloadResultsPanel links={links} />;
}

/** Inner panel — separated so hooks run unconditionally (hooks cannot follow early returns). */
function DownloadResultsPanel({ links }: { links: DownloadLink[] }) {
  const download = useMutation({
    mutationFn: ({ url }: { url: string; label: string }) => fetchBlobDownload(url),
    onSuccess: (_data, { label }) => notifySuccess(`Downloaded ${label}`),
    onError: (error) => notifyError(error as Problem),
  });

  return (
    <Card className="hf-download-results">
      <CardHeader className="pb-0">
        <Eyebrow>Export</Eyebrow>
        <CardTitle>Download Results</CardTitle>
      </CardHeader>
      <Separator className="mx-6" />
      <CardContent className="flex flex-col gap-2">
        {links.map(({ label, href, icon: Icon, variant }) => (
          <Button
            key={href}
            variant={variant}
            size="sm"
            className="justify-start"
            disabled={download.isPending}
            onClick={() => download.mutate({ url: href, label })}
          >
            <Icon className="size-4 shrink-0" strokeWidth={1.5} />
            {label}
          </Button>
        ))}
      </CardContent>
    </Card>
  );
}
