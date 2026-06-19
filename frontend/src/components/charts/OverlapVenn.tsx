/**
 * OverlapVenn — dependency-free two-circle SVG Venn diagram.
 *
 * Renders a schematic Venn where circle radii scale with set size and each
 * region is labeled with its target count. Designed as a replacement for the
 * server-rendered stage5_venn.png: pure SVG so ChartFrame can serialize it
 * directly for the Download PNG export path.
 *
 * Colors come from useChartColors() so the exported PNG carries resolved
 * hf-* values, never unresolved CSS variable references.
 */

import { useChartColors } from "@/lib/chartTheme";

type Props = {
  compoundCount: number;
  diseaseCount: number;
  overlapCount: number;
};

export function OverlapVenn({ compoundCount, diseaseCount, overlapCount }: Props) {
  const colors = useChartColors();

  // Guard derived region counts against negatives from bad data.
  const onlyCompound = Math.max(0, compoundCount - overlapCount);
  const onlyDisease = Math.max(0, diseaseCount - overlapCount);

  // Radii scale with set size relative to the larger set.
  const maxCount = Math.max(compoundCount, diseaseCount, 1);
  const radius = (c: number) => Math.max(28, Math.sqrt(c / maxCount) * 92);
  const rA = radius(compoundCount);
  const rB = radius(diseaseCount);

  // Overlap distance: partial overlap gives a readable lens intersection.
  const d = (rA + rB) * 0.62;
  const cy = 140;
  const cxA = 230 - d / 2;
  const cxB = 230 + d / 2;

  // Label positions: region counts sit in the visual center of each region.
  const labelCompound = { x: cxA - rA * 0.45, y: cy };
  const labelOverlap = { x: 230, y: cy };
  const labelDisease = { x: cxB + rB * 0.45, y: cy };

  // Set-name labels sit above each circle center.
  const nameA = { x: cxA, y: cy - rA - 10 };
  const nameB = { x: cxB, y: cy - rB - 10 };

  return (
    <svg
      viewBox="0 0 460 280"
      style={{ width: "100%", display: "block" }}
      aria-label="Target overlap"
    >
      <title>Target overlap</title>

      {/* Circle A — compound targets (sage) */}
      <circle
        cx={cxA}
        cy={cy}
        r={rA}
        fill={colors.sage}
        fillOpacity={0.42}
        stroke={colors.sage}
        strokeWidth={1.5}
      />

      {/* Circle B — disease targets (terracotta) */}
      <circle
        cx={cxB}
        cy={cy}
        r={rB}
        fill={colors.terracotta}
        fillOpacity={0.42}
        stroke={colors.terracotta}
        strokeWidth={1.5}
      />

      {/* Region count labels */}
      <text
        x={labelCompound.x}
        y={labelCompound.y}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={18}
        fontWeight={600}
        fill={colors.fg1}
      >
        {onlyCompound}
      </text>

      <text
        x={labelOverlap.x}
        y={labelOverlap.y}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={18}
        fontWeight={600}
        fill={colors.fg1}
      >
        {overlapCount}
      </text>

      <text
        x={labelDisease.x}
        y={labelDisease.y}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={18}
        fontWeight={600}
        fill={colors.fg1}
      >
        {onlyDisease}
      </text>

      {/* Set-name labels */}
      <text
        x={nameA.x}
        y={nameA.y}
        textAnchor="middle"
        dominantBaseline="auto"
        fontSize={12}
        fill={colors.fg2}
      >
        Compound targets
      </text>

      <text
        x={nameB.x}
        y={nameB.y}
        textAnchor="middle"
        dominantBaseline="auto"
        fontSize={12}
        fill={colors.fg2}
      >
        Disease targets
      </text>
    </svg>
  );
}
