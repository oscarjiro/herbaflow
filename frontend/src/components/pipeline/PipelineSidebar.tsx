import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { StageNavItem } from './StageNavItem'
import type { StageNavItemProps } from './StageNavItem'
import type { AnalysisStatusResponse, AnalysisRunResponse } from '@/types/api'

const STAGE_NAMES = [
  'Compound Selection',
  'ADME Screening',
  'Target Identification',
  'Disease Targets',
  'Target Overlap',
  'PPI Network',
  'Hub Gene Analysis',
  'Pathway Enrichment',
]

function getStageStatus(
  stageNum: number,
  statusData: AnalysisStatusResponse | undefined,
): StageNavItemProps['status'] {
  if (!statusData) return 'future'
  const s = statusData.status
  const cur = statusData.current_stage ?? 0
  if (stageNum < cur) return 'completed'
  if (stageNum === cur) {
    if (s.includes('awaiting_approval')) return 'awaiting_approval'
    if (s.includes('running')) return 'running'
    if (s.includes('complete')) return 'completed'
    if (s.includes('failed')) return 'future'
  }
  return 'future'
}

export interface PipelineSidebarProps {
  status: AnalysisStatusResponse | undefined
  analysis: AnalysisRunResponse | undefined
  activeStage: number | null
  onStageClick: (stage: number) => void
}

export function PipelineSidebar({
  status,
  analysis,
  activeStage,
  onStageClick,
}: PipelineSidebarProps) {
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const navigate = useNavigate()

  function handleNewAnalysis() {
    localStorage.removeItem('hf_last_analysis_id')
    navigate('/analysis')
  }

  const sidebarContent = (
    <div className="w-[220px] shrink-0 flex flex-col bg-hf-surface-2 border-r border-hf-border h-screen sticky top-0">
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-hf-border space-y-1.5">
        <p className="text-sm font-medium text-hf-fg1 truncate">
          {analysis?.analysis_name ?? 'Loading...'}
        </p>
        <StatusBadge
          status={status?.mode ?? 'guided'}
          label={status?.mode === 'auto' ? 'Auto' : 'Guided'}
        />
      </div>

      {/* Stage list */}
      <nav className="flex-1 overflow-y-auto py-1">
        {STAGE_NAMES.map((name, index) => {
          const stageNumber = index + 1
          const stageStatus = getStageStatus(stageNumber, status)
          const isClickable =
            stageStatus === 'completed' ||
            stageStatus === 'running' ||
            stageStatus === 'awaiting_approval'

          return (
            <StageNavItem
              key={stageNumber}
              stageNumber={stageNumber}
              name={name}
              status={stageStatus}
              isActive={activeStage === stageNumber}
              onClick={isClickable ? () => onStageClick(stageNumber) : undefined}
            />
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-hf-border">
        <button
          type="button"
          onClick={handleNewAnalysis}
          className="text-xs text-hf-fg3 hover:text-hf-fg1 transition-colors px-4 py-3 w-full text-left"
        >
          New Analysis
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop sidebar — always visible at md+ */}
      <div className="hidden md:block">{sidebarContent}</div>

      {/* Mobile hamburger button */}
      <button
        type="button"
        onClick={() => setIsMobileOpen(true)}
        className="md:hidden fixed top-3 left-3 z-40 p-2 rounded bg-hf-surface-2 border border-hf-border text-hf-fg2 hover:text-hf-fg1 transition-colors"
        aria-label="Open navigation"
      >
        <Menu className="w-4 h-4" />
      </button>

      {/* Mobile overlay + drawer */}
      {isMobileOpen && (
        <>
          {/* Backdrop */}
          <div
            className="md:hidden fixed inset-0 z-40 bg-black/40"
            onClick={() => setIsMobileOpen(false)}
          />
          {/* Drawer */}
          <div className="md:hidden fixed inset-y-0 left-0 z-50">
            <div className="relative">
              {sidebarContent}
              <button
                type="button"
                onClick={() => setIsMobileOpen(false)}
                className="absolute top-3 right-3 p-1 rounded text-hf-fg3 hover:text-hf-fg1 transition-colors"
                aria-label="Close navigation"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </>
  )
}
