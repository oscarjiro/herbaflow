/**
 * CTP (compound-target-pathway) graph helpers.
 *
 * Extracted from RunView so they are independently unit-testable.
 * All three exports are pure functions: no hooks, no side effects.
 */

import type cytoscape from "cytoscape";
import type { CtpGraph, CtpGraphNode, CtpGraphEdge } from "../api/types.gen";
import type { ChartColors } from "./chartTheme";

// ---------------------------------------------------------------------------
// Concentric layout
// ---------------------------------------------------------------------------

/** Rank map: higher = closer to the centre of the concentric circles. */
const RANK: Record<string, number> = {
  target: 3,
  compound: 2,
  pathway: 1,
  disease: 1,
};

/**
 * Returns a Cytoscape concentric layout that ranks nodes by biological role:
 * targets at the core, compounds in the middle ring, pathways/diseases on the
 * outer ring. This mirrors the reference figure's layered view.
 */
export function ctpConcentricLayout(): cytoscape.LayoutOptions {
  return {
    name: "concentric",
    // The cast is necessary because the LayoutOptions union is narrowly typed
    // at the cytoscape-core level; concentric options exist at runtime.
    ...({
      concentric: (n: { data: (key: string) => string }) => RANK[n.data("type")] ?? 0,
      levelWidth: () => 1,
      minNodeSpacing: 28,
      animate: false,
    } as Record<string, unknown>),
  };
}

// ---------------------------------------------------------------------------
// Stylesheet
// ---------------------------------------------------------------------------

/**
 * Build the Cytoscape stylesheet for the CTP graph from resolved hf-* color
 * strings. Follows the reference palette:
 *   - Compound  → warning (yellow)  round-rectangle
 *   - Target    → info (blue)       ellipse
 *   - Hub       → sageDeep          ellipse (enlarged)
 *   - Disease   → danger (red)      round-rectangle
 *   - Pathway   → danger (red)      round-rectangle
 * Edges carry directed triangle arrows with a bezier curve.
 */
export function buildCtpStylesheet(colors: ChartColors): cytoscape.StylesheetJson {
  return [
    // ---- base node style --------------------------------------------------
    {
      selector: "node",
      style: {
        label: "data(label)",
        color: colors.fg1,
        // Surface-coloured halo keeps labels legible over dense nodes/edges and
        // in either theme (re-resolves with the stylesheet on theme toggle).
        "text-outline-color": colors.surface,
        "text-outline-width": 2,
        "font-size": 9,
        "font-weight": 600,
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 2,
        width: 20,
        height: 20,
      },
    },
    // ---- per-type node styles --------------------------------------------
    {
      selector: 'node[type = "compound"]',
      style: {
        "background-color": colors.warning,
        shape: "round-rectangle",
      },
    },
    {
      selector: 'node[type = "target"]',
      style: {
        "background-color": colors.info,
        shape: "ellipse",
      },
    },
    {
      selector: 'node[type = "target"][hub = "true"]',
      style: {
        "background-color": colors.sageDeep,
        width: 30,
        height: 30,
      },
    },
    {
      selector: 'node[type = "disease"]',
      style: {
        "background-color": colors.danger,
        shape: "round-rectangle",
      },
    },
    {
      selector: 'node[type = "pathway"]',
      style: {
        "background-color": colors.danger,
        shape: "round-rectangle",
      },
    },
    // ---- edge styles -------------------------------------------------------
    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "target-arrow-color": colors.fg3,
        "line-color": colors.border,
        opacity: 0.6,
      },
    },
    {
      selector: 'edge[interaction = "compound-target"]',
      style: {
        "line-color": colors.border,
        "target-arrow-color": colors.fg3,
        "line-style": "solid",
      },
    },
    {
      selector: 'edge[interaction = "target-pathway"]',
      style: {
        "line-color": colors.fg3,
        "target-arrow-color": colors.fg3,
        "line-style": "dashed",
      },
    },
  ] as cytoscape.StylesheetJson;
}

// ---------------------------------------------------------------------------
// Element builder
// ---------------------------------------------------------------------------

/**
 * Build a flat Cytoscape elements array from the typed CTP graph.
 * Nodes carry id/label/type/hub; edges carry id/source/target/interaction.
 * Logic is unchanged from the original RunView inline version.
 */
export function buildCtpElements(graph: CtpGraph): cytoscape.ElementDefinition[] {
  const nodes: cytoscape.ElementDefinition[] = (graph.nodes as CtpGraphNode[]).map((n) => ({
    data: { id: n.id, label: n.label, type: n.type, hub: n.is_hub },
  }));
  const edges: cytoscape.ElementDefinition[] = (graph.edges as CtpGraphEdge[]).map((e, i) => ({
    data: { id: `e-${i}`, source: e.source, target: e.target, interaction: e.interaction },
  }));
  return [...nodes, ...edges];
}
