import {
  exportAllResultsUrl,
  exportNetworkBundleUrl,
  exportReportUrl,
  exportStagesBundleUrl,
} from "../lib/exportUrl";

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
  const links: [string, string][] = [
    ["Report (.md)", exportReportUrl(analysisId)],
    ...(hasCompounds
      ? ([["Network & docking (.zip)", exportNetworkBundleUrl(analysisId)]] as [string, string][])
      : []),
    ["All stages (.zip)", exportStagesBundleUrl(analysisId)],
    ["All results (.zip)", exportAllResultsUrl(analysisId)],
  ];
  return (
    <div className="hf-download-results">
      {links.map(([label, href]) => (
        <a key={href} href={href} download>
          {label}
        </a>
      ))}
    </div>
  );
}
