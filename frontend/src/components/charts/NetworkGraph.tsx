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

import { useRef } from "react";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import CytoscapeComponent from "react-cytoscapejs";
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
}: NetworkGraphProps) {
  const cyRef = useRef<cytoscape.Core | null>(null);

  return (
    <ChartFrame
      title={title}
      filename={filename}
      description={description}
      onExport={async () => {
        if (cyRef.current) {
          await exportCytoscapeAsPng(cyRef.current, { title, filename });
        }
      }}
    >
      <div style={{ height: height ?? 420, width: "100%" }}>
        <CytoscapeComponent
          elements={elements}
          stylesheet={stylesheet}
          layout={layout ?? DEFAULT_LAYOUT}
          cy={(cy) => {
            cyRef.current = cy;
          }}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      {tray}
    </ChartFrame>
  );
}
