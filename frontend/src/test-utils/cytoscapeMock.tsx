import React from "react";

/**
 * Shared jsdom mock for `react-cytoscapejs` — the single home for the fake
 * cytoscape Core, so the test files that render a graph never re-declare it.
 *
 * Register it from a test file with:
 *   vi.mock("react-cytoscapejs", () => import("@/test-utils/cytoscapeMock"));
 *
 * The stub Core is chainable and exposes exactly the methods `NetworkGraph`
 * touches: `png` (export), `on`/`off` (tooltip wiring), `style` (theme
 * re-apply on toggle), `zoom`/`width`/`height`/`fit`/`center` (the zoom
 * controls), and `nodes().style`/`removeStyle` (the export label override).
 * It renders a `data-testid="cytoscape"` div carrying the element count so
 * callers can assert the elements were passed through.
 */
export default function CytoscapeMock({
  cy,
  elements,
}: {
  cy?: (c: unknown) => void;
  elements?: unknown[];
}) {
  const core: Record<string, unknown> = {
    png: () => "data:image/png;base64,AAAA",
    style: () => core,
    zoom: () => 1,
    width: () => 600,
    height: () => 400,
    fit: () => core,
    center: () => core,
    nodes: () => ({ style: () => {}, removeStyle: () => {} }),
  };
  core.on = () => core;
  core.off = () => core;
  cy?.(core);
  return React.createElement("div", {
    "data-testid": "cytoscape",
    "data-count": String(elements?.length ?? 0),
  });
}
