import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAnalysisStatus } from '@/hooks/useAnalysisStatus'
import { useAnalysis } from '@/hooks/useAnalysis'
import { useApproveStage } from '@/hooks/useApproveStage'
import { useResetFromStage } from '@/hooks/useResetFromStage'
import { PipelineSidebar } from '@/components/pipeline/PipelineSidebar'
import { ApprovalBar } from '@/components/shared/ApprovalBar'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { StageSkeletonLoader } from '@/components/shared/StageSkeletonLoader'
import { Stage1Panel } from '@/components/stages/Stage1Panel'
import { Stage2Panel } from '@/components/stages/Stage2Panel'
import { Stage3Panel } from '@/components/stages/Stage3Panel'
import { Stage4Panel } from '@/components/stages/Stage4Panel'
import { Stage5Panel } from '@/components/stages/Stage5Panel'
import { Stage6Panel } from '@/components/stages/Stage6Panel'
import { Stage7Panel } from '@/components/stages/Stage7Panel'
import { Stage8Panel } from '@/components/stages/Stage8Panel'
import { SkippedStageNotice } from '@/components/shared/SkippedStageNotice'
import { UserProvidedNotice } from '@/components/shared/UserProvidedNotice'
import { getStageState, getStageInputs } from '@/types/api'
import type { AnalysisStatusResponse, AnalysisRunResponse } from '@/types/api'

// ============================================================================
// Stage panel registry
// ============================================================================

interface StageStubProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

const STAGE_COMPONENTS: Record<number, React.ComponentType<StageStubProps>> = {
  1: Stage1Panel,
  2: Stage2Panel,
  3: Stage3Panel,
  4: Stage4Panel,
  5: Stage5Panel,
  6: Stage6Panel,
  7: Stage7Panel,
  8: Stage8Panel,
}

// ============================================================================
// StagePanelRouter
// ============================================================================

interface StagePanelRouterProps {
  stage: number | null
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

function StagePanelRouter({ stage, analysis, status, analysisId }: StagePanelRouterProps) {
  const approveMutation = useApproveStage(analysisId)
  const resetMutation = useResetFromStage(analysisId)

  if (stage === null) {
    return <EmptyState message="Select a stage from the sidebar" />
  }

  const StageComponent = STAGE_COMPONENTS[stage]
  if (!StageComponent) {
    return <EmptyState message={`Stage ${stage} is not available`} />
  }

  const stageResult = analysis?.stage_results[`stage_${stage}`]
  const stageState = getStageState(stageResult)

  if (stageState === 'not_applicable') {
    return <SkippedStageNotice />
  }

  const isStageFailed =
    status?.current_stage === stage &&
    status?.status === `stage_${stage}_failed`

  if (isStageFailed) {
    return (
      <div className="p-8">
        <ErrorState message={status?.error_message ?? `Stage ${stage} failed. Check backend logs for details.`} />
      </div>
    )
  }

  // Show skeleton while stage is actively running (results not yet available)
  const isStageRunning = status?.status === `stage_${stage}_running`
  if (isStageRunning) {
    const progressText =
      stage === 3 ? 'Identifying targets across ChEMBL, PubChem BioAssay…' : undefined
    return (
      <div className="p-2">
        <StageSkeletonLoader stage={stage} progressText={progressText} />
      </div>
    )
  }

  const isAwaitingApproval =
    status?.mode === 'guided' &&
    status?.status === `stage_${stage}_awaiting_approval`

  return (
    <div>
      {stageState === 'user_provided' && (
        <UserProvidedNotice inputs={getStageInputs(stageResult)} />
      )}
      <StageComponent
        stage={stage}
        analysis={analysis}
        status={status}
        analysisId={analysisId}
      />
      {isAwaitingApproval && (
        <ApprovalBar
          onApprove={(overrides) => approveMutation.mutate(overrides)}
          onRedo={() => {
            if (!window.confirm('Redo this stage? Current results will be overwritten.')) return
            resetMutation.mutate({ stage })
          }}
          isLoading={approveMutation.isPending || resetMutation.isPending}
          nextStage={stage + 1}
          currentParams={analysis?.parameters ?? null}
        />
      )}
    </div>
  )
}

// ============================================================================
// Error helpers
// ============================================================================

// api.ts throws expired-analysis (HTTP 410 Gone) as a plain Error whose message
// is formatted `API 410: <body>` (see lib/api.ts). Until that error shape carries
// a status code, the message prefix is the only reliable signal — this helper
// keeps the brittle string check in one place.
function isGoneError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith('API 410:')
}

// ============================================================================
// Expiry helpers
// ============================================================================

function formatExpiryTime(ms: number): string {
  const totalMinutes = Math.floor(ms / 60_000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes} minute${minutes !== 1 ? 's' : ''}`
}

// ============================================================================
// PipelinePage
// ============================================================================

export default function PipelinePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeStage, setActiveStage] = useState<number | null>(null)

  const { data: status, isError: statusError } = useAnalysisStatus(id!)
  const { data: analysis, isError: analysisIsError, error: analysisError } = useAnalysis(id!)

  // Tick every minute so the expiry countdown stays current while the page is open
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(interval)
  }, [])

  // ms until expiry; null if no expiry set
  const msUntilExpiry = useMemo(() => {
    if (!analysis?.expires_at) return null
    return new Date(analysis.expires_at).getTime() - now
  }, [analysis?.expires_at, now])

  // Auto-focus current stage when status advances
  useEffect(() => {
    if (status?.current_stage != null) {
      setActiveStage(status.current_stage)
    }
  }, [status?.current_stage])

  // Invalidate analysis cache on every status change so stage_results are
  // always fresh — prevents stale panel data in auto mode when the sidebar
  // has already advanced to the next stage.
  useEffect(() => {
    if (status?.status) {
      void queryClient.invalidateQueries({ queryKey: ['analysis', id] })
    }
  }, [status?.status, id, queryClient])

  // Expired analysis — 410 Gone
  if (analysisIsError && isGoneError(analysisError)) {
    return (
      <div className="p-8">
        <div className="rounded-lg border border-hf-border bg-hf-surface p-8 text-center">
          <h2 className="mb-2 text-xl font-semibold text-hf-fg1">Analysis Expired</h2>
          <p className="mb-6 text-hf-fg2">
            Results are retained for 24 hours after completion. This analysis has expired.
          </p>
          <button
            type="button"
            className="rounded-md border border-hf-border bg-hf-surface px-4 py-2 text-sm text-hf-fg1 hover:text-hf-fg2"
            onClick={() => {
              localStorage.removeItem('hf_last_analysis_id')
              navigate('/analysis')
            }}
          >
            Start New Analysis
          </button>
        </div>
      </div>
    )
  }

  // Terminal failure — show error
  if (status?.status === 'failed') {
    return (
      <div className="p-8">
        <ErrorState
          message={status.error_message}
          onNewAnalysis={() => {
            localStorage.removeItem('hf_last_analysis_id')
            navigate('/analysis')
          }}
        />
      </div>
    )
  }

  // Terminal rejection — show rejected state
  if (status?.status && /^stage_\d+_rejected$/.test(status.status)) {
    const match = status.status.match(/stage_(\d+)_rejected/)
    const stageLabel = match ? `Stage ${match[1]}` : 'a stage'
    return (
      <div className="p-8">
        <div className="rounded-lg border border-hf-border bg-hf-surface p-8 text-center">
          <h2 className="mb-2 text-xl font-semibold text-hf-fg1">Analysis Rejected</h2>
          <p className="mb-6 text-hf-fg2">{stageLabel} was rejected. Start a new analysis to try again.</p>
          <button
            type="button"
            className="rounded-md border border-hf-border bg-hf-surface px-4 py-2 text-sm text-hf-fg1 hover:text-hf-fg2"
            onClick={() => {
              localStorage.removeItem('hf_last_analysis_id')
              navigate('/analysis')
            }}
          >
            Start New Analysis
          </button>
        </div>
      </div>
    )
  }

  // Backend unreachable or persistent API error
  if (statusError) {
    return (
      <div className="p-8">
        <ErrorState
          message="Unable to reach the server. Check that the backend is running."
          onNewAnalysis={() => {
            localStorage.removeItem('hf_last_analysis_id')
            navigate('/analysis')
          }}
        />
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <PipelineSidebar
        status={status}
        analysis={analysis}
        activeStage={activeStage}
        onStageClick={setActiveStage}
      />
      <main className="flex-1 overflow-y-auto p-6">
        {msUntilExpiry !== null && msUntilExpiry > 0 && msUntilExpiry < 2 * 60 * 60 * 1000 && (
          <div className="mb-4 rounded-md border border-hf-border bg-hf-surface px-4 py-3 text-sm text-hf-fg2">
            ⚠️ Results expire in{' '}
            <span className="font-medium text-hf-fg1">
              {formatExpiryTime(msUntilExpiry)}
            </span>
            . Export your data before they are deleted.
          </div>
        )}
        <StagePanelRouter
          stage={activeStage}
          analysis={analysis}
          status={status}
          analysisId={id!}
        />
      </main>
    </div>
  )
}
