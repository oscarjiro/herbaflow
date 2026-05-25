import { useRef, useState, useCallback, useMemo } from 'react'
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import CytoscapeComponent from 'react-cytoscapejs'
import fcose from 'cytoscape-fcose'
import Cytoscape from 'cytoscape'
import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { StageParamsPanel } from '@/components/shared/StageParamsPanel'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage6Result } from '@/types/api'

Cytoscape.use(fcose)

const SOURCES = [
  {
    name: 'STRING-DB',
    url: 'https://string-db.org/',
    description: 'Protein–protein interaction network database. Interactions filtered to human (taxon 9606) at the configured confidence threshold (default 0.4 = medium confidence). Edge weight proportional to combined interaction score (0–1).',
    citation: 'Szklarczyk D et al. (2023). The STRING database in 2023: protein–protein association networks for any of 12 000+ organisms. Nucleic Acids Res 51(D1):D638–D646.',
  },
]

interface Stage6PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

type LayoutName = 'fcose' | 'grid' | 'circle'

// Stylesheet uses `as any` on the ref and stylesheet prop to avoid conflicts
// between @types/cytoscape and react-cytoscapejs typings.
// Cytoscape renders to canvas — CSS custom properties do not resolve there.
// Use raw hex values derived from the design system tokens.
// --hf-fg-4 (#9A958C), --hf-sage (#8FA084), --hf-fg-1 (#1A1A1A), --hf-bg (#F7F5F2)
const styleSheet = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-size': '10px',
      'text-valign': 'center',
      'text-halign': 'center',
      width: 30,
      height: 30,
      'background-color': '#9A958C',
      color: '#1A1A1A',
    },
  },
  {
    selector: 'node[type="hub"]',
    style: { 'background-color': '#8FA084', color: '#1A1A1A', width: 40, height: 40 },
  },
  {
    selector: 'node[type="overlap"]',
    style: { 'background-color': '#1A1A1A', color: '#F7F5F2' },
  },
  {
    selector: 'node.dimmed',
    style: { opacity: 0.2 },
  },
  {
    selector: 'edge',
    style: {
      // mapData scales weight (0–1 combined_score) to 1–6px width
      width: 'mapData(weight, 0, 1, 1, 6)',
      'line-color': '#C8C4BC',
      opacity: 0.6,
    },
  },
  {
    selector: 'edge.dimmed',
    style: { opacity: 0.05 },
  },
]

const LAYOUTS: Record<LayoutName, cytoscape.LayoutOptions> = {
  fcose: { name: 'fcose', animate: true, randomize: true, fit: true } as cytoscape.LayoutOptions,
  grid: { name: 'grid', animate: true, fit: true } as cytoscape.LayoutOptions,
  circle: { name: 'circle', animate: true, fit: true } as cytoscape.LayoutOptions,
}

export function Stage6Panel({ stage, analysis, status, analysisId }: Stage6PanelProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cyRef = useRef<any>(null)
  const [layout, setLayout] = useState<LayoutName>('fcose')
  const [tooltip, setTooltip] = useState<{ gene: string; degree: number } | null>(null)

  const result = analysis?.stage_results[`stage_${stage}`] as Stage6Result | null | undefined

  // Combine nodes and edges for Cytoscape — must be before any conditional return
  const elements = useMemo(
    () => (result ? [...result.nodes, ...result.edges] : []),
    [result]
  )

  const handleLayoutChange = useCallback((newLayout: LayoutName) => {
    setLayout(newLayout)
    if (cyRef.current) {
      cyRef.current.layout(LAYOUTS[newLayout]).run()
    }
  }, [])

  const handleFit = useCallback(() => {
    cyRef.current?.fit()
  }, [])

  const handleExportPng = useCallback(() => {
    if (!cyRef.current) return
    const dataUrl = cyRef.current.png({ output: 'blob-promise', scale: 2 })
    Promise.resolve(dataUrl)
      .then((blob: Blob) => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'ppi-network.png'
        a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => { /* export failed silently */ })
  }, [])

  if (!result) {
    return (
      <div className="space-y-6">
        <StageHeader stage={6} name="PPI Network" status={status?.status ?? 'pending'} elapsedSeconds={null} />
        <EmptyState message="Stage 6 results not yet available" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <StageHeader stage={6} name="PPI Network" status={status?.status ?? 'complete'} elapsedSeconds={null} />

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Nodes" value={result.node_count} />
        <StatCard label="Edges" value={result.edge_count} />
      </div>

      <StageParamsPanel
        stage={6}
        analysisId={analysisId}
        currentParams={analysis?.parameters ?? null}
        canRerun={status?.mode === 'guided'}
      />

      {/* Controls */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-hf-fg3">Layout:</span>
        {(['fcose', 'grid', 'circle'] as LayoutName[]).map((l) => (
          <button
            key={l}
            onClick={() => handleLayoutChange(l)}
            className={`px-2 py-1 rounded-sm text-xs border transition-colors ${
              layout === l
                ? 'bg-hf-fg1 text-white border-hf-fg1'
                : 'bg-hf-surface text-hf-fg2 border-hf-border hover:border-hf-border-strong'
            }`}
          >
            {l}
          </button>
        ))}
        <button
          onClick={handleFit}
          className="px-2 py-1 rounded-sm text-xs border bg-hf-surface text-hf-fg2 border-hf-border hover:border-hf-border-strong ml-auto"
        >
          Fit
        </button>
        <button
          onClick={handleExportPng}
          className="px-2 py-1 rounded-sm text-xs border bg-hf-surface text-hf-fg2 border-hf-border hover:border-hf-border-strong"
        >
          Export PNG
        </button>
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-xs text-hf-fg3">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full" style={{ background: 'var(--hf-sage)' }} />
          Hub gene
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full" style={{ background: 'var(--hf-fg-1)' }} />
          Overlap target
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full bg-hf-fg4" />
          Other
        </span>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div className="text-xs text-hf-fg2 bg-hf-surface border border-hf-border rounded px-2 py-1 w-fit">
          {tooltip.gene} — degree: {tooltip.degree ?? 'N/A'}
        </div>
      )}

      {/* Cytoscape canvas */}
      <div className="rounded-lg border border-hf-border overflow-hidden" style={{ height: 480 }}>
        <CytoscapeComponent
          elements={elements}
          stylesheet={styleSheet as any} // eslint-disable-line @typescript-eslint/no-explicit-any
          layout={LAYOUTS[layout]}
          style={{ width: '100%', height: '100%' }}
          cy={(cy: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
            cy.removeAllListeners()
            cyRef.current = cy

            cy.on('mouseover', 'node', (e: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
              const node = e.target
              setTooltip({ gene: node.data('label') as string, degree: node.data('degree') as number })
            })
            cy.on('mouseout', 'node', () => {
              setTooltip(null)
            })
            cy.on('tap', 'node', (e: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
              const node = e.target
              cy.elements().addClass('dimmed')
              node.removeClass('dimmed')
              node.neighborhood().removeClass('dimmed')
            })
            cy.on('tap', (e: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
              if (e.target === cy) {
                cy.elements().removeClass('dimmed')
              }
            })
          }}
        />
      </div>

      {/* Node type legend note */}
      <div className="space-y-1 text-xs text-hf-fg3 font-sans">
        <p>Click a node to highlight its neighbourhood. Click background to reset.</p>
        <p>
          <span className="font-medium text-hf-fg2">Source:</span> STRING-DB protein–protein interactions (combined score 0–1, min. confidence threshold: {result.min_confidence}) ·{' '}
          <span className="font-medium text-hf-fg2">Edge weight:</span> score × 5 + 1 (range 1–6, thicker = higher confidence)
        </p>
        <p>
          <span className="font-medium text-hf-fg2">Hub criterion:</span> overlap gene with degree &gt; µ + σ (mean + 1 SD of degree distribution). Hub+Bottleneck additionally requires betweenness &gt; µ + σ.
        </p>
      </div>

      <DataSources sources={SOURCES} />
    </div>
  )
}
