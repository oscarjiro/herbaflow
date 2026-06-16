import type { ElementType } from "react";
import { Download, FileText, FolderArchive, Network } from "lucide-react";
import {
  exportAllResultsUrl,
  exportNetworkBundleUrl,
  exportReportUrl,
  exportStagesBundleUrl,
} from "../lib/exportUrl";
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

/** Download panel — shown only once the run is complete. Binary downloads via the
 * browser (Content-Disposition from the backend), not the typed SDK. */
export function DownloadResults({
  status,
  analysisId,
  hasCompounds = true,
}: {
  status: string | null | undefined;
  analysisId: string;
  hasCompounds?: boolean;
}) {
  if (status !== "complete") return null;

  // The network-and-docking bundle holds compound-target-pathway and docking artifacts only;
  // a target-only run has none, and the backend 404s that bundle, so do not offer it. The PPI
  // network stays available via the stages and all-results bundles.
  const links: DownloadLink[] = [
    {
      label: "Report (.md)",
      href: exportReportUrl(analysisId),
      icon: FileText,
      variant: "default",
    },
    ...(hasCompounds
      ? ([
          {
            label: "Network & docking (.zip)",
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

  return (
    <Card className="hf-download-results">
      <CardHeader className="pb-0">
        <Eyebrow>Export</Eyebrow>
        <CardTitle>Download Results</CardTitle>
      </CardHeader>
      <Separator className="mx-6" />
      <CardContent className="flex flex-col gap-2">
        {links.map(({ label, href, icon: Icon, variant }) => (
          <Button key={href} variant={variant} size="sm" asChild className="justify-start">
            <a href={href} download>
              <Icon className="size-4 shrink-0" strokeWidth={1.5} />
              {label}
            </a>
          </Button>
        ))}
      </CardContent>
    </Card>
  );
}
