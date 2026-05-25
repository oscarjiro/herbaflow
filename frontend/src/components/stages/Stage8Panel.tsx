import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
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

function PathwayChart({ terms }: { terms: PathwayTerm[] }) {
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
  )
}

export function Stage8Panel({ stage, analysis, status, analysisId }: Stage8PanelProps) {
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
        </TabsList>

        {SOURCES.map((src) => (
          <TabsContent key={src} value={src}>
            <div className="mt-4">
              <h3 className="text-sm font-medium text-hf-fg2 mb-3">{SOURCE_LABELS[src]}</h3>
              <PathwayChart terms={termsBySource[src]} />
            </div>
          </TabsContent>
        ))}
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
