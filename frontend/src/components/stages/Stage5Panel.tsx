import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage5Result } from '@/types/api'

const SOURCES = [
  {
    name: 'SciPy',
    url: 'https://scipy.org/',
    description: 'Statistical computing library. Hypergeometric distribution used for gene-set overlap significance testing (equivalent to Fisher\'s exact test for one-sided 2×2 tables). Background = human proteome size (N = 20,000).',
    citation: 'Virtanen P et al. (2020). SciPy 1.0: fundamental algorithms for scientific computing in Python. Nature Methods 17:261–272.',
  },
]

interface Stage5PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

interface VennProps {
  compoundOnly: number
  overlap: number
  diseaseOnly: number
}

function VennDiagram({ compoundOnly, overlap, diseaseOnly }: VennProps) {
  const W = 280, H = 160, r = 70, offset = 45
  const cx1 = W / 2 - offset / 2
  const cx2 = W / 2 + offset / 2
  const cy  = H / 2
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex justify-between text-xs font-medium text-hf-fg2" style={{ width: W }}>
        <span style={{ marginLeft: 8 }}>Compound Targets</span>
        <span style={{ marginRight: 8 }}>Disease Targets</span>
      </div>
      <svg width={W} height={H} className="mx-auto" role="img" aria-label="Venn diagram showing target overlap">
        <circle cx={cx1} cy={cy} r={r} fill="var(--hf-sage-soft)" opacity={0.7} />
        <circle cx={cx2} cy={cy} r={r} fill="var(--hf-info-soft)" opacity={0.7} />
        <text x={cx1 - offset} y={cy} textAnchor="middle" fontSize={12} dominantBaseline="middle">{compoundOnly}</text>
        <text x={W / 2} y={cy} textAnchor="middle" fontSize={12} fontWeight={600} dominantBaseline="middle">{overlap}</text>
        <text x={cx2 + offset} y={cy} textAnchor="middle" fontSize={12} dominantBaseline="middle">{diseaseOnly}</text>
      </svg>
      <div className="flex gap-16 text-xs text-hf-fg3">
        <span>Compound only</span>
        <span>Overlap</span>
        <span>Disease only</span>
      </div>
    </div>
  )
}

export function Stage5Panel({ stage, analysis, status }: Stage5PanelProps) {
  const result = analysis?.stage_results[`stage_${stage}`] as Stage5Result | null | undefined

  if (!result) {
    return (
      <div className="space-y-6">
        <StageHeader stage={5} name="Target Overlap" status={status?.status ?? 'pending'} elapsedSeconds={null} />
        <EmptyState message="Stage 5 results not yet available" />
      </div>
    )
  }

  const significanceState: 'significant' | 'not_significant' | 'na' =
    result.p_value == null ? 'na'
    : (result.significant ?? result.p_value < 0.05) ? 'significant'
    : 'not_significant'

  return (
    <div className="space-y-6">
      <StageHeader stage={5} name="Target Overlap" status={status?.status ?? 'complete'} elapsedSeconds={null} />

      <div className="rounded-lg bg-hf-surface p-6 border border-hf-border">
        <VennDiagram
          compoundOnly={result.compound_only_count}
          overlap={result.overlap_count}
          diseaseOnly={result.disease_only_count}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Jaccard Index" value={result.jaccard != null && !Number.isNaN(result.jaccard) ? result.jaccard.toFixed(3) : 'N/A'} />
        <StatCard label="Fisher's Exact p-value" value={result.p_value != null ? result.p_value.toExponential(2) : 'N/A'} />
        <div className="rounded-lg bg-hf-surface border border-hf-border p-4 flex flex-col gap-1">
          <span className="text-xs text-hf-fg3">Significance</span>
          <span
            className={`inline-block px-2 py-0.5 rounded text-xs font-medium w-fit ${
              significanceState === 'significant'
                ? 'bg-hf-success-soft text-hf-success'
                : significanceState === 'not_significant'
                ? 'bg-hf-warning-soft text-hf-warning'
                : 'bg-hf-surface-2 text-hf-fg3'
            }`}
          >
            {significanceState === 'significant' ? 'Significant'
              : significanceState === 'not_significant' ? 'Not Significant'
              : 'N/A'}
          </span>
        </div>
      </div>

      {result.overlap_count === 0 && (
        <div className="rounded-lg bg-hf-warning-soft border border-hf-warning px-4 py-3">
          <p className="text-sm font-medium text-hf-warning">No pharmacological overlap detected</p>
          <p className="text-xs text-hf-fg2 mt-1">
            No compound targets overlap with disease targets. Downstream network analysis (Stages 6–8) has limited pharmacological validity.
            Consider lowering the pChEMBL threshold or selecting plants with known activity against this disease.
          </p>
        </div>
      )}

      <p className="text-xs text-hf-fg3 font-sans">
        Jaccard index = overlap / (compound-only + overlap + disease-only). Statistical significance by Fisher's exact test (hypergeometric model, background = human proteome).
      </p>

      <div>
        <h3 className="text-sm font-medium text-hf-fg1 mb-3">
          Overlap Genes ({(result.overlap ?? []).length})
        </h3>
        {(result.overlap ?? []).length === 0 ? (
          <EmptyState message="No overlapping targets found" />
        ) : (
          <div className="flex flex-wrap gap-2">
            {(result.overlap ?? []).map((gene) => (
              <span
                key={gene}
                className="px-2 py-0.5 rounded text-xs font-mono bg-hf-surface-2 text-hf-fg2 border border-hf-border"
              >
                {gene}
              </span>
            ))}
          </div>
        )}
      </div>

      <DataSources sources={SOURCES} />
    </div>
  )
}
