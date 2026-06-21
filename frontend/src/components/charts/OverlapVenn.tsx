/**
 * OverlapVenn — area-proportional two-set Venn via @upsetjs/react.
 *
 * @upsetjs is element-based: a circle's area scales with its element count and
 * the lens area with the count of elements SHARED between the two sets. We only
 * receive cardinalities (compound-side / disease-side target counts + the
 * overlap size) plus, optionally, the real shared gene symbols. To make the
 * auto-computed intersection come out to exactly the overlap size, we synthesize
 * element-id arrays: a pool of shared ids that appear in BOTH sets, padded with
 * per-side unique ids so each set's total length equals its real count.
 *
 * Real overlap gene symbols are used as the shared ids first (so they carry
 * meaning and surface on hover), padded with synthetic ids only when there are
 * fewer named genes than the overlap count.
 *
 * Colors come from useChartColors() as resolved hf-* strings so the serialized
 * SVG export carries concrete values, never unresolved CSS variable references.
 * Renders SVG, so ChartFrame's default Download-PNG path serializes it directly.
 * Same component name + a superset of the prior props (adds optional
 * overlapGenes), so the Stage 5 call site is unchanged.
 */

import type { FC } from "react";
import { useMemo } from "react";
import { VennDiagram as RawVennDiagram, asSets, type VennDiagramProps } from "@upsetjs/react";
import { useChartColors, readChartFontFamily } from "@/lib/chartTheme";

// @upsetjs/react ships React 18 types; under React 19 its generic
// `<T>(p) => ReactElement` signature is not assignable to JSX.ElementType
// (the stricter ReactPortal.children rule). Re-type it as a plain FC over the
// string-element prop shape we use; the runtime component is unchanged.
const VennDiagram = RawVennDiagram as unknown as FC<VennDiagramProps<string>>;

type Props = {
  compoundCount: number;
  diseaseCount: number;
  overlapCount: number;
  /** Real shared gene symbols; used as the intersection element ids when present. */
  overlapGenes?: string[];
};

/**
 * Build the two @upsetjs sets from cardinalities by synthesizing element ids.
 *
 * The shared ids are the SAME string values in both sets' elems arrays — that
 * is what makes the auto-computed distinct intersection equal `overlapCount`.
 */
function buildVennSets(
  compoundCount: number,
  diseaseCount: number,
  overlapCount: number,
  overlapGenes: string[] | undefined,
  sageColor: string,
  terracottaColor: string,
) {
  // Defensive clamps: counts are non-negative integers; the overlap cannot
  // exceed the smaller set.
  const compound = Math.max(0, Math.floor(compoundCount));
  const disease = Math.max(0, Math.floor(diseaseCount));
  const overlap = Math.max(0, Math.min(Math.floor(overlapCount), compound, disease));

  // Shared element ids: prefer real gene symbols (meaningful + hover), then pad
  // with synthetic unique ids up to `overlap`. Truncate if there are more genes
  // than the overlap count.
  const named = (overlapGenes ?? []).slice(0, overlap);
  const sharedIds: string[] = [...named];
  for (let i = named.length; i < overlap; i += 1) {
    sharedIds.push(`__shared_${i}`);
  }

  // Per-side unique ids fill the remainder so each set's length is exact.
  const compoundOnly: string[] = [];
  for (let i = 0; i < compound - overlap; i += 1) {
    compoundOnly.push(`__c_${i}`);
  }
  const diseaseOnly: string[] = [];
  for (let i = 0; i < disease - overlap; i += 1) {
    diseaseOnly.push(`__d_${i}`);
  }

  const compoundElems = [...compoundOnly, ...sharedIds]; // length === compound
  const diseaseElems = [...diseaseOnly, ...sharedIds]; // length === disease

  return asSets([
    { name: "Compound targets", elems: compoundElems, color: sageColor },
    { name: "Disease targets", elems: diseaseElems, color: terracottaColor },
  ]);
}

export function OverlapVenn({ compoundCount, diseaseCount, overlapCount, overlapGenes }: Props) {
  const colors = useChartColors();
  // Match the site sans instead of @upsetjs's default font; empty -> library default.
  const fontFamily = useMemo(() => readChartFontFamily() || undefined, []);

  const sets = useMemo(
    () =>
      buildVennSets(
        compoundCount,
        diseaseCount,
        overlapCount,
        overlapGenes,
        colors.sage,
        colors.terracotta,
      ),
    [compoundCount, diseaseCount, overlapCount, overlapGenes, colors.sage, colors.terracotta],
  );

  // Centre the fixed-size SVG in the (wider) chart card; the padding keeps the
  // corner-anchored set labels inside the canvas while the larger width/height
  // keeps the circles a readable size. textColor drives the set labels,
  // valueTextColor the counts; both track the theme via useChartColors.
  return (
    <div className="flex w-full justify-center">
      <VennDiagram
        sets={sets}
        width={620}
        height={380}
        padding={84}
        fontFamily={fontFamily}
        exportButtons={false}
        textColor={colors.fg1}
        valueTextColor={colors.fg1}
        strokeColor={colors.border}
      />
    </div>
  );
}
