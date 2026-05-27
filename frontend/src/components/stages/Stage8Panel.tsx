import React, { useRef } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ScatterChart, Scatter, ZAxis, CartesianGrid, Legend } from 'recharts'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { SkippedStageNotice } from '@/components/shared/SkippedStageNotice'
import { StageParamsPanel } from '@/components/shared/StageParamsPanel'
import { isSkippedStage } from '@/types/api'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage8Result, PathwayTerm, PathwaySource } from '@/types/api'

const DATA_SOURCES = [
  {
    name: 'g:Profiler',
    url: 'https://biit.cs.ut.ee/gprofiler/',
    description: 'Over-representation analysis (ORA) across GO (BP, MF, CC) and KEGG pathway databases. Input: hub genes from Stage 7. Background: all compound targets from Stage 3 (the study protein universe). FDR corrected via Benjamini–Hochberg.',
    citation: 'Raudvere U et al. (2019). g:Profiler: a web server for functional enrichment analysis and conversions of gene lists. Nucleic Acids Res 47(W1):W191–W198.',
  },
]

interface Stage8PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

const SOURCES: PathwaySource[] = ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG']

const SOURCE_LABELS: Record<PathwaySource, string> = {
  'GO:BP': 'GO: Biological Process',
  'GO:MF': 'GO: Molecular Function',
  'GO:CC': 'GO: Cellular Component',
  'KEGG': 'KEGG Pathways',
}

interface ChartEntry {
  name: string
  value: number
  fdr: number
  term_name: string
  intersection_size: number
}

function exportChartPng(containerEl: HTMLDivElement | null, filename: string) {
  if (!containerEl) return
  const svg = containerEl.querySelector('svg')
  if (!svg) return
  const svgData = new XMLSerializer().serializeToString(svg)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const img = new Image()
  img.onload = () => {
    canvas.width = img.naturalWidth * 2
    canvas.height = img.naturalHeight * 2
    ctx.scale(2, 2)
    ctx.drawImage(img, 0, 0)
    canvas.toBlob((blob) => {
      if (!blob) return
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = filename
      link.click()
      URL.revokeObjectURL(link.href)
    })
  }
  img.src = URL.createObjectURL(new Blob([svgData], { type: 'image/svg+xml' }))
}

function PathwayChart({ terms, chartRef }: { terms: PathwayTerm[]; chartRef?: React.RefObject<HTMLDivElement | null> }) {
  if (terms.length === 0) {
    return <EmptyState message="No significant pathways found for this category" />
  }

  const safeTerms = terms.filter((t) => t.fdr != null && t.fdr >= 0 && t.fdr <= 1)

  const chartData: ChartEntry[] = safeTerms
    .sort((a, b) => a.fdr - b.fdr)
    .slice(0, 20)
    .map((t) => ({
      name: t.term_name.length > 40 ? t.term_name.slice(0, 40) + '…' : t.term_name,
      value: t.fdr > 0 ? Math.max(1, -Math.log10(t.fdr)) : 1,
      fdr: t.fdr,
      term_name: t.term_name,
      intersection_size: t.intersection_size,
    }))

  return (
    <div ref={chartRef}>
      <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 24)}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 60, bottom: 24, left: 8 }}>
          <XAxis
            type="number"
            label={{ value: '-log₁₀(FDR)', position: 'insideBottom', offset: -12, fontSize: 11 }}
            tick={{ fontSize: 10 }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={200}
            tick={{ fontSize: 10 }}
          />
          <ReferenceLine
            x={1.301}
            stroke="var(--hf-danger)"
            strokeDasharray="4 2"
            label={{ value: 'FDR=0.05', position: 'top', fontSize: 9, fill: 'var(--hf-danger)' }}
          />
          <Bar dataKey="value" fill="var(--hf-sage)" radius={[0, 2, 2, 0]} />
          <Tooltip
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(_value: unknown, _name: unknown, props: any) => {
              const entry = props.payload as ChartEntry | undefined
              return [
                `FDR: ${entry?.fdr?.toExponential(2) ?? '—'}  |  genes: ${entry?.intersection_size ?? '—'}`,
                entry?.term_name ?? '',
              ]
            }}
            contentStyle={{
              fontSize: '11px',
              background: 'var(--hf-surface)',
              border: '1px solid var(--hf-border)',
              borderRadius: '4px',
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

const BUBBLE_COLORS: Record<PathwaySource, string> = {
  'GO:BP': 'var(--hf-sage)',
  'GO:MF': 'var(--hf-terracotta)',
  'GO:CC': 'var(--hf-accent)',
  'KEGG': 'var(--hf-warning)',
}

interface BubbleEntry {
  x: number       // gene_ratio = intersection_size / term_size
  y: number       // -log10(p_value)
  z: number       // intersection_size (bubble size)
  name: string
  source: PathwaySource
  p_value: number
  fdr: number
  intersection_size: number
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function BubbleTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload as BubbleEntry | undefined
  if (!d) return null
  return (
    <div
      style={{
        fontSize: '11px',
        background: 'var(--hf-surface)',
        border: '1px solid var(--hf-border)',
        borderRadius: '4px',
        padding: '6px 8px',
        maxWidth: '240px',
      }}
    >
      <p style={{ fontWeight: 600, marginBottom: 2, wordBreak: 'break-word' }}>{d.name}</p>
      <p>Source: {d.source}</p>
      <p>p-value: {d.p_value?.toExponential(2)}</p>
      <p>FDR: {d.fdr?.toExponential(2)}</p>
      <p>Gene count: {d.intersection_size}</p>
      <p>Gene ratio: {d.x?.toFixed(3)}</p>
    </div>
  )
}

function EnrichmentBubbleChart({
  termsBySource,
  chartRef,
}: {
  termsBySource: Record<PathwaySource, PathwayTerm[]>
  chartRef?: React.RefObject<HTMLDivElement | null>
}) {
  const allTerms = SOURCES.flatMap((src) =>
    termsBySource[src]
      .filter((t) => t.p_value != null && t.p_value > 0 && t.term_size > 0)
      .slice(0, 15)
      .map((t): BubbleEntry => ({
        x: t.intersection_size / t.term_size,
        y: -Math.log10(t.p_value),
        z: t.intersection_size,
        name: t.term_name,
        source: src,
        p_value: t.p_value,
        fdr: t.fdr,
        intersection_size: t.intersection_size,
      }))
  )

  if (allTerms.length === 0) {
    return <EmptyState message="No significant pathways available for bubble chart" />
  }

  const bySource = SOURCES.reduce<Record<PathwaySource, BubbleEntry[]>>(
    (acc, src) => {
      acc[src] = allTerms.filter((d) => d.source === src)
      return acc
    },
    { 'GO:BP': [], 'GO:MF': [], 'GO:CC': [], 'KEGG': [] }
  )

  return (
    <div ref={chartRef}>
      <ResponsiveContainer width="100%" height={420}>
        <ScatterChart margin={{ top: 16, right: 24, bottom: 40, left: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--hf-border)" />
          <XAxis
            type="number"
            dataKey="x"
            name="Gene Ratio"
            domain={[0, 'auto']}
            label={{ value: 'Gene Ratio', position: 'insideBottom', offset: -24, fontSize: 11 }}
            tick={{ fontSize: 10 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="−log₁₀(p-value)"
            label={{ value: '−log₁₀(p-value)', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }}
            tick={{ fontSize: 10 }}
          />
          <ZAxis type="number" dataKey="z" range={[30, 300]} name="Gene Count" />
          <Tooltip content={<BubbleTooltip />} />
          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
          {SOURCES.map((src) =>
            bySource[src].length > 0 ? (
              <Scatter
                key={src}
                name={SOURCE_LABELS[src]}
                data={bySource[src]}
                fill={BUBBLE_COLORS[src]}
                fillOpacity={0.75}
              />
            ) : null
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

export function Stage8Panel({ stage, analysis, status, analysisId }: Stage8PanelProps) {
  const chartRefGoBp = useRef<HTMLDivElement | null>(null)
  const chartRefGoMf = useRef<HTMLDivElement | null>(null)
  const chartRefGoCc = useRef<HTMLDivElement | null>(null)
  const chartRefKegg = useRef<HTMLDivElement | null>(null)
  const chartRefBubble = useRef<HTMLDivElement | null>(null)
  const chartRefs: Record<PathwaySource, React.RefObject<HTMLDivElement | null>> = {
    'GO:BP': chartRefGoBp,
    'GO:MF': chartRefGoMf,
    'GO:CC': chartRefGoCc,
    'KEGG': chartRefKegg,
  }

  const rawResult = analysis?.stage_results[`stage_${stage}`]
  const result = rawResult as Stage8Result | null | undefined

  if (isSkippedStage(rawResult)) {
    return (
      <div className="space-y-6">
        <StageHeader stage={stage} name="Pathway Enrichment" status={status?.status ?? 'pending'} elapsedSeconds={null} />
        <SkippedStageNotice />
      </div>
    )
  }

  if (!result) {
    return (
      <div className="space-y-6">
        <StageHeader stage={stage} name="Pathway Enrichment" status={status?.status ?? 'pending'} elapsedSeconds={null} />
        <EmptyState message="Stage 8 results not yet available" />
      </div>
    )
  }

  const termsBySource: Record<PathwaySource, PathwayTerm[]> = {
    'GO:BP': result.go_bp ?? [],
    'GO:MF': result.go_mf ?? [],
    'GO:CC': result.go_cc ?? [],
    'KEGG': result.kegg ?? [],
  }
  const totalTerms = Object.values(termsBySource).reduce((s, a) => s + a.length, 0)

  return (
    <div className="space-y-6">
      <StageHeader stage={stage} name="Pathway Enrichment" status={status?.status ?? 'complete'} elapsedSeconds={null} />

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Significant Pathways" value={result.total_significant} />
        <StatCard label="Total Terms" value={totalTerms} />
      </div>

      <StageParamsPanel
        stage={8}
        analysisId={analysisId}
        currentParams={analysis?.parameters ?? null}
        canRerun={status?.mode === 'guided'}
      />

      <Tabs defaultValue="GO:BP">
        <TabsList>
          {SOURCES.map((src) => (
            <TabsTrigger key={src} value={src}>
              {src}
              {termsBySource[src].length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs bg-hf-sage-soft text-hf-sage-deep font-medium">
                  {termsBySource[src].length}
                </span>
              )}
            </TabsTrigger>
          ))}
          <TabsTrigger value="bubble">Bubble</TabsTrigger>
        </TabsList>

        {SOURCES.map((src) => (
          <TabsContent key={src} value={src}>
            <div className="mt-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-hf-fg2">{SOURCE_LABELS[src]}</h3>
                <button
                  type="button"
                  onClick={() => exportChartPng(chartRefs[src].current, `enrichment-${src.toLowerCase().replace(':', '-')}-${analysisId}.png`)}
                  className="rounded-sm border border-hf-border px-3 py-1.5 text-xs text-hf-fg2 hover:text-hf-fg1"
                >
                  Export PNG
                </button>
              </div>
              <PathwayChart terms={termsBySource[src]} chartRef={chartRefs[src]} />
            </div>
          </TabsContent>
        ))}

        <TabsContent value="bubble">
          <div className="mt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-hf-fg2">All Sources — Bubble Chart</h3>
              <button
                type="button"
                onClick={() => exportChartPng(chartRefBubble.current, `enrichment-bubble-${analysisId}.png`)}
                className="rounded-sm border border-hf-border px-3 py-1.5 text-xs text-hf-fg2 hover:text-hf-fg1"
              >
                Export PNG
              </button>
            </div>
            <p className="text-xs text-hf-fg3 mb-3 font-sans">
              Top 15 terms per source. Bubble size = gene count. Axes: x = gene ratio (intersection / term size), y = −log₁₀(p-value).
            </p>
            <EnrichmentBubbleChart termsBySource={termsBySource} chartRef={chartRefBubble} />
          </div>
        </TabsContent>
      </Tabs>

      <div className="space-y-1 text-xs text-hf-fg3 font-sans">
        <p>Showing top 20 terms per category by -log₁₀(FDR). Dashed line = FDR 0.05 significance threshold.</p>
        <p>
          <span className="font-medium text-hf-fg2">Method:</span> g:Profiler ORA (over-representation analysis) ·{' '}
          <span className="font-medium text-hf-fg2">Background:</span> human proteome ·{' '}
          <span className="font-medium text-hf-fg2">Correction:</span> Benjamini–Hochberg FDR
        </p>
      </div>

      <DataSources sources={DATA_SOURCES} />
    </div>
  )
}
