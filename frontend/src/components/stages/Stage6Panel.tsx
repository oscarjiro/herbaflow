import { useRef, useState, useCallback, useMemo } from 'react'
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import CytoscapeComponent from 'react-cytoscapejs'
import fcose from 'cytoscape-fcose'
import Cytoscape from 'cytoscape'
import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { EmptyState } from '@/components/shared/EmptyState'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage6Result } from '@/types/api'

Cytoscape.use(fcose)

interface Stage6PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

type LayoutName = 'fcose' | 'grid' | 'circle'

// Stylesheet uses `as any` on the ref and stylesheet prop to avoid conflicts
// between @types/cytoscape and react-cytoscapejs typings.
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
      'background-color': 'var(--hf-fg-4)',
      color: 'var(--hf-fg-1)',
    },
  },
  {
    selector: 'node[type="hub"]',
    style: { 'background-color': 'var(--hf-sage)', color: 'var(--primary-foreground)', width: 40, height: 40 },
  },
  {
    selector: 'node[type="overlap"]',
    style: { 'background-color': 'var(--hf-fg-1)', color: 'var(--primary-foreground)' },
  },
  {
    selector: 'node.dimmed',
    style: { opacity: 0.2 },
  },
  {
    selector: 'edge',
    style: {
      width: 'data(weight)',
      'line-color': 'var(--hf-border-strong)',
      opacity: 0.6,
    },
  },
  {
    selector: 'edge.dimmed',
    style: { opacity: 0.05 },
  },
]

const LAYOUTS: Record<LayoutName, cytoscape.LayoutOptions> = {
  fcose: { name: 'fcose', animate: true, randomize: false } as cytoscape.LayoutOptions,
  grid: { name: 'grid', animate: true } as cytoscape.LayoutOptions,
  circle: { name: 'circle', animate: true } as cytoscape.LayoutOptions,
}

export function Stage6Panel({ stage, analysis, status }: Stage6PanelProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cyRef = useRef<any>(null)
  const [layout, setLayout] = useState<LayoutName>('fcose')
  const [tooltip, setTooltip] = useState<{ gene: string; degree: number } | null>(null)

  const result = analysis?.stage_results[String(stage)] as Stage6Result | null | undefined

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
          <span className="inline-block w-3 h-3 rounded-full bg-hf-fg1" />
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
          {tooltip.gene} — degree: {tooltip.degree}
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
      <p className="text-xs text-hf-fg4">
        Click a node to highlight its neighbourhood. Click background to reset.
      </p>
    </div>
  )
}
