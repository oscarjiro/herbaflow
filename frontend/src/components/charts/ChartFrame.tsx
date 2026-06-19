import { useRef, useState } from "react";
import { DownloadIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { exportSvgAsPng } from "@/lib/chartExport";
import { notifyError, notifySuccess } from "@/lib/toast";
import type { Problem } from "@/lib/problem";

type ChartFrameProps = {
  /** Chart title shown in the card header and embedded in the exported PNG. */
  title: string;
  /** Filename (including .png extension) used when saving the export. */
  filename: string;
  /** Optional one-line description rendered below the title in muted text. */
  description?: string;
  /**
   * Custom export handler. When provided it is called instead of the default
   * SVG-to-PNG path. Useful for canvas-based charts (e.g. Cytoscape) that
   * manage their own export.
   */
  onExport?: () => Promise<void>;
  children: React.ReactNode;
};

/**
 * Titled card container for interactive charts.
 *
 * Provides a consistent header (title + description) and a single
 * "Download PNG" control wired to either a custom onExport handler or the
 * shared exportSvgAsPng path. All chart components wrap their content in this
 * frame rather than each implementing their own download button.
 */
export function ChartFrame({ title, filename, description, onExport, children }: ChartFrameProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);

  async function handleDownload() {
    setIsExporting(true);
    try {
      if (onExport) {
        await onExport();
      } else {
        const svg = wrapperRef.current?.querySelector("svg");
        if (!svg) throw new Error("No chart to export");
        await exportSvgAsPng(svg as SVGSVGElement, { title, filename });
      }
      notifySuccess(`Downloaded ${title}`);
    } catch (err) {
      notifyError(err as Problem);
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardAction>
          <Button
            variant="outline"
            size="sm"
            disabled={isExporting}
            onClick={() => void handleDownload()}
          >
            <DownloadIcon className="size-4 shrink-0" strokeWidth={1.5} />
            Download PNG
          </Button>
        </CardAction>
        {description && (
          <p className="text-muted-foreground col-span-full text-sm">{description}</p>
        )}
      </CardHeader>
      <CardContent>
        <div ref={wrapperRef}>{children}</div>
      </CardContent>
    </Card>
  );
}
