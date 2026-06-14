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
}: {
  status: string | null | undefined;
  analysisId: string;
}) {
  if (status !== "complete") return null;
  const links: [string, string][] = [
    ["Report (.md)", exportReportUrl(analysisId)],
    ["Network & docking (.zip)", exportNetworkBundleUrl(analysisId)],
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
