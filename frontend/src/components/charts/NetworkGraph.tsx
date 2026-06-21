/**
 * NetworkGraph — the one reusable Cytoscape graph home.
 *
 * Generic on purpose: it knows nothing about protein networks specifically. The
 * caller builds a flat elements array (nodes + edges) and a stylesheet (from
 * resolved hf-* colors, since Cytoscape cannot read CSS variables) and passes
 * them in. The Stage-6 PPI view uses it today; the RunView compound-target-pathway
 * graph reuses it with different elements and styling.
 *
 * Wraps the shared ChartFrame so the titled card and the Download-PNG control
 * are identical to every other chart. Export goes through the canvas onExport
 * seam to exportCytoscapeAsPng (cy.png -> shared compose helper).
 *
 * Pan and zoom are Cytoscape's built-in user interactions; no extra config.
 */

import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import CytoscapeComponent from "react-cytoscapejs";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { ChartFrame } from "./ChartFrame";
import { exportCytoscapeAsPng } from "@/lib/chartExport";

// Register the fcose layout once at module load, guarded against double-register.
let registered = false;
if (!registered) {
  cytoscape.use(fcose);
  registered = true;
}

type NetworkGraphProps = {
  /** Title shown in the card header and baked into the exported PNG. */
  title: string;
  /** Filename (with .png) used when saving the export. */
  filename: string;
  /** Flat array of node + edge element definitions (caller-built). */
  elements: cytoscape.ElementDefinition[];
  /** Cytoscape stylesheet, built from resolved hf-* color strings. */
  stylesheet: cytoscape.StylesheetJson;
  /** Optional layout override; defaults to fcose. */
  layout?: cytoscape.LayoutOptions;
  /** Optional content rendered below the graph (e.g. an isolated-node strip). */
  tray?: React.ReactNode;
  /** Optional one-line description rendered under the title. */
  description?: string;
  /** Graph canvas height in pixels (default 420). */
  height?: number;
  /**
   * Optional hover tooltip producer. Receives the hovered node's data object
   * and returns the string to display in the positioned label.
   */
  nodeTooltip?: (nodeData: Record<string, unknown>) => string;
  /** Optional content rendered below the graph canvas (e.g. a colour legend). */
  legend?: React.ReactNode;
};

const DEFAULT_LAYOUT: cytoscape.LayoutOptions = {
  name: "fcose",
  // fcose-specific options are accepted at runtime; cast keeps the typed core happy.
  ...({ animate: false, randomize: true, nodeRepulsion: 6500 } as Record<string, unknown>),
};

export function NetworkGraph({
  title,
  filename,
  elements,
  stylesheet,
  layout,
  tray,
  description,
  height,
  nodeTooltip,
  legend,
}: NetworkGraphProps) {
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [tip, setTip] = useState<{ text: string; x: number; y: number } | null>(null);

  // react-cytoscapejs only applies the stylesheet prop at mount, so a theme
  // toggle (which produces a new resolved-colour stylesheet) would leave the
  // live graph with stale label/edge colours. Re-apply it whenever it changes.
  useEffect(() => {
    cyRef.current?.style(stylesheet);
  }, [stylesheet]);

  const zoomByFactor = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  };
  const fitToView = () => cyRef.current?.fit(undefined, 24);

  return (
    <ChartFrame
      title={title}
      filename={filename}
      description={description}
      onExport={async () => {
        if (cyRef.current) {
          await exportCytoscapeAsPng(cyRef.current, { filename });
        }
      }}
    >
      <div style={{ height: height ?? 420, width: "100%", position: "relative" }}>
        <CytoscapeComponent
          elements={elements}
          stylesheet={stylesheet}
          layout={layout ?? DEFAULT_LAYOUT}
          cy={(cy) => {
            cyRef.current = cy;
            if (nodeTooltip) {
              // react-cytoscapejs may invoke this callback again with the same
              // Core on re-renders, so clear any prior node listeners before
              // re-binding — keeps registration idempotent (no handler buildup).
              cy.off("mouseover", "node").on("mouseover", "node", (evt: cytoscape.EventObject) => {
                const pos = evt.renderedPosition ?? { x: 0, y: 0 };
                setTip({
                  text: nodeTooltip(evt.target.data() as Record<string, unknown>),
                  x: pos.x,
                  y: pos.y,
                });
              });
              cy.off("mouseout", "node").on("mouseout", "node", () => setTip(null));
            }
          }}
          style={{ width: "100%", height: "100%" }}
        />
        {tip !== null && (
          <div
            style={{
              position: "absolute",
              left: tip.x + 8,
              top: tip.y + 8,
              padding: "4px 8px",
              borderRadius: 4,
              fontSize: "0.75rem",
              pointerEvents: "none",
              zIndex: 10,
              whiteSpace: "nowrap",
            }}
            className="bg-hf-surface text-hf-fg1 border-hf-border border shadow-sm"
          >
            {tip.text}
          </div>
        )}
        <div className="absolute top-2 right-2 z-10 flex flex-col gap-1">
          <button
            type="button"
            aria-label="Zoom in"
            onClick={() => zoomByFactor(1.2)}
            className="bg-hf-surface text-hf-fg-2 border-hf-border hover:bg-hf-bg flex h-7 w-7 items-center justify-center rounded-md border shadow-sm"
          >
            <ZoomIn size={16} strokeWidth={1.5} />
          </button>
          <button
            type="button"
            aria-label="Zoom out"
            onClick={() => zoomByFactor(1 / 1.2)}
            className="bg-hf-surface text-hf-fg-2 border-hf-border hover:bg-hf-bg flex h-7 w-7 items-center justify-center rounded-md border shadow-sm"
          >
            <ZoomOut size={16} strokeWidth={1.5} />
          </button>
          <button
            type="button"
            aria-label="Fit to view"
            onClick={fitToView}
            className="bg-hf-surface text-hf-fg-2 border-hf-border hover:bg-hf-bg flex h-7 w-7 items-center justify-center rounded-md border shadow-sm"
          >
            <Maximize2 size={16} strokeWidth={1.5} />
          </button>
        </div>
      </div>
      {legend}
      {tray}
    </ChartFrame>
  );
}
