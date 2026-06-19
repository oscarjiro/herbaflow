/**
 * Minimal ambient types for two cytoscape packages that ship no usable type
 * surface for our usage:
 *
 *  - react-cytoscapejs@2.0.0 ships no .d.ts and has no @types package.
 *  - cytoscape-fcose@2.2.0 ships no .d.ts (it is a layout extension passed to
 *    cytoscape.use()).
 *
 * Both are typed loosely on purpose: the one consumer (NetworkGraph) only needs
 * the props/registration it actually uses. Cytoscape itself bundles its own
 * types, so its named types are imported from "cytoscape".
 */
declare module "react-cytoscapejs" {
  import type { ComponentType, CSSProperties } from "react";
  import type { Core, ElementDefinition, StylesheetJson, LayoutOptions } from "cytoscape";

  export interface CytoscapeComponentProps {
    elements: ElementDefinition[];
    stylesheet?: StylesheetJson;
    layout?: LayoutOptions;
    cy?: (cy: Core) => void;
    style?: CSSProperties;
    className?: string;
    id?: string;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}

declare module "cytoscape-fcose" {
  import type { Ext } from "cytoscape";
  const fcose: Ext;
  export default fcose;
}
