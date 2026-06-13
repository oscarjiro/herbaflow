import { exportBundleUrl } from "../lib/exportUrl";

/** "Download results" link — shown only once the run is complete. Binary download via the
 * browser (Content-Disposition from the backend), not the typed SDK. */
export function DownloadResults({
  status,
  analysisId,
}: {
  status: string | null | undefined;
  analysisId: string;
}) {
  if (status !== "complete") return null;
  return (
    <a className="hf-download-results" href={exportBundleUrl(analysisId)} download>
      Download results
    </a>
  );
}
