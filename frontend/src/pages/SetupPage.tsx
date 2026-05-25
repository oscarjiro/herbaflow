import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { PlantSelector } from '@/components/setup/PlantSelector'
import { DiseaseSelector } from '@/components/setup/DiseaseSelector'
import { ModeToggle } from '@/components/setup/ModeToggle'
import { AdvancedParameters, DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'
import type { AdvancedParams } from '@/components/setup/AdvancedParameters'
import { useStartAnalysis } from '@/hooks/useStartAnalysis'
import { api } from '@/lib/api'
import { isTerminalStatus } from '@/types/api'

// ============================================================================
// Helpers
// ============================================================================

function generateDefaultName(): string {
  const date = new Date().toISOString().slice(0, 10) // 'YYYY-MM-DD'
  return `Analysis — ${date}`
}

// ============================================================================
// SetupPage
// ============================================================================

export default function SetupPage() {
  const navigate = useNavigate()
  const mutation = useStartAnalysis()

  // Form state
  const [name, setName] = useState(() => generateDefaultName())
  const [plantIds, setPlantIds] = useState<string[]>([])
  const [diseaseIds, setDiseaseIds] = useState<string[]>([])
  const [mode, setMode] = useState<'guided' | 'auto'>('guided')
  const [params, setParams] = useState<AdvancedParams>(DEFAULT_PARAMS)

  // Cache restore: if there's an in-progress analysis, redirect to it
  useEffect(() => {
    const lastId = localStorage.getItem('hf_last_analysis_id')
    if (!lastId) return
    api
      .getAnalysisStatus(lastId)
      .then((status) => {
        // Redirect for in-progress OR completed analyses; leave failed/rejected on setup page
        if (!isTerminalStatus(status.status) || status.status === 'complete') {
          navigate(`/analysis/${lastId}`, { replace: true })
        }
      })
      .catch(() => {
        // Analysis not found or network error — clear stale cache
        localStorage.removeItem('hf_last_analysis_id')
      })
  }, [navigate])

  // Derived state
  const isDisabled =
    plantIds.length === 0 || diseaseIds.length === 0 || mutation.isPending

  function handleSubmit() {
    if (isDisabled) return
    mutation.mutate({
      name,
      mode,
      plant_ids: plantIds,
      disease_ids: diseaseIds,
      parameters: params as unknown as Record<string, unknown>,
    })
  }

  return (
    <div className="max-w-2xl mx-auto py-12 px-6">
      <h1 className="font-display text-3xl text-hf-fg1 mb-8">New Analysis</h1>

      {/* Analysis Name */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Analysis Name</p>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter analysis name"
          className="border-hf-border bg-hf-surface text-hf-fg1"
        />
      </div>

      {/* Plants */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Plants</p>
        <PlantSelector value={plantIds} onChange={setPlantIds} />
      </div>

      {/* Disease */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Diseases</p>
        <DiseaseSelector value={diseaseIds} onChange={setDiseaseIds} />
      </div>

      {/* Mode */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Mode</p>
        <ModeToggle value={mode} onChange={setMode} />
      </div>

      {/* Advanced Parameters */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Advanced Parameters</p>
        <AdvancedParameters value={params} onChange={setParams} />
      </div>

      {/* Error message */}
      {mutation.isError && (
        <div className="text-hf-danger text-sm mt-2">
          {mutation.error?.message}
        </div>
      )}

      {/* Submit */}
      <Button
        className="w-full mt-2"
        disabled={isDisabled}
        onClick={handleSubmit}
      >
        {mutation.isPending ? 'Starting...' : 'Start Analysis'}
      </Button>
    </div>
  )
}
