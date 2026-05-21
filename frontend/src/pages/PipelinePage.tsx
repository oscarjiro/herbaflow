import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAnalysisStatus } from '@/hooks/useAnalysisStatus'
import { useAnalysis } from '@/hooks/useAnalysis'
import { useApproveStage } from '@/hooks/useApproveStage'
import { useRejectStage } from '@/hooks/useRejectStage'
import { PipelineSidebar } from '@/components/pipeline/PipelineSidebar'
import { ApprovalBar } from '@/components/shared/ApprovalBar'
import { ErrorState } from '@/components/shared/ErrorState'
import { EmptyState } from '@/components/shared/EmptyState'
import { Stage1Panel } from '@/components/stages/Stage1Panel'
import { Stage2Panel } from '@/components/stages/Stage2Panel'
import { Stage3Panel } from '@/components/stages/Stage3Panel'
import { Stage4Panel } from '@/components/stages/Stage4Panel'
import { Stage5Panel } from '@/components/stages/Stage5Panel'
import { Stage6Panel } from '@/components/stages/Stage6Panel'
import { Stage7Panel } from '@/components/stages/Stage7Panel'
import { Stage8Panel } from '@/components/stages/Stage8Panel'
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
  const rejectMutation = useRejectStage(analysisId)

  if (stage === null) {
    return <EmptyState message="Select a stage from the sidebar" />
  }

  const StageComponent = STAGE_COMPONENTS[stage]
  if (!StageComponent) {
    return <EmptyState message={`Stage ${stage} is not available`} />
  }

  const isAwaitingApproval =
    status?.mode === 'guided' &&
    status?.status === `stage_${stage}_awaiting_approval`

  return (
    <div>
      <StageComponent
        stage={stage}
        analysis={analysis}
        status={status}
        analysisId={analysisId}
      />
      {isAwaitingApproval && (
        <ApprovalBar
          onApprove={() => approveMutation.mutate()}
          onReject={() => rejectMutation.mutate()}
          isLoading={approveMutation.isPending || rejectMutation.isPending}
        />
      )}
    </div>
  )
}

// ============================================================================
// PipelinePage
// ============================================================================

export default function PipelinePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeStage, setActiveStage] = useState<number | null>(null)

  const { data: status } = useAnalysisStatus(id!)
  const { data: analysis } = useAnalysis(id!)

  // Auto-focus current stage when status advances
  useEffect(() => {
    if (status?.current_stage != null) {
      setActiveStage(status.current_stage)
    }
  }, [status?.current_stage])

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

  return (
    <div className="flex h-screen overflow-hidden">
      <PipelineSidebar
        status={status}
        analysis={analysis}
        activeStage={activeStage}
        onStageClick={setActiveStage}
      />
      <main className="flex-1 overflow-y-auto p-6">
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
