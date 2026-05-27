import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { CreateAnalysisRequest } from '@/types/api'

export interface StartAnalysisOptions {
  request: CreateAnalysisRequest
  /** SMILES/InChI strings to inject after creation (manual_compounds mode). */
  compounds?: string[]
  /** Gene symbols or UniProt accessions to inject after creation (manual_targets mode). */
  targets?: string[]
}

export function useStartAnalysis() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: async ({ request, compounds, targets }: StartAnalysisOptions) => {
      const { analysis_id } = await api.createAnalysis(request)

      let failedCompounds = 0
      let failedTargets = 0
      let duplicatesRemoved = 0
      let duplicateNames: string[] = []

      if (compounds && compounds.length > 0) {
        const injectResult = await api.injectCompounds(analysis_id, compounds)
        if (injectResult.injected === 0) {
          throw new Error('No valid compounds found. Please check your SMILES/InChI strings.')
        }
        failedCompounds = injectResult.failed.length
        duplicatesRemoved = injectResult.duplicates_removed
        duplicateNames = injectResult.duplicate_names
      }

      if (targets && targets.length > 0) {
        const injectResult = await api.injectTargets(analysis_id, targets)
        if (injectResult.injected === 0) {
          throw new Error('No valid targets found. Please check your gene symbols or UniProt accessions.')
        }
        failedTargets = injectResult.failed.length
      }

      return { analysis_id, failedCompounds, failedTargets, duplicatesRemoved, duplicateNames }
    },
    onSuccess: (data) => {
      localStorage.setItem('hf_last_analysis_id', data.analysis_id)
      if (data.failedCompounds > 0 || data.failedTargets > 0) {
        console.warn(
          `Analysis started with partial injection failures — ` +
          `${data.failedCompounds} compound(s) and ${data.failedTargets} target(s) discarded.`
        )
      }
      if (data.duplicatesRemoved > 0) {
        console.warn(
          `${data.duplicatesRemoved} duplicate compound(s) removed: ${data.duplicateNames.join(', ')}`
        )
      }
      navigate(`/analysis/${data.analysis_id}`)
    },
  })
}
