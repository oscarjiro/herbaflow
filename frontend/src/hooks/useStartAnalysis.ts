import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { CreateAnalysisRequest } from '@/types/api'

export interface StartAnalysisOptions {
  request: CreateAnalysisRequest
  /** SMILES/InChI strings to inject after creation (manual_compounds mode). */
  compounds?: string[]
}

export function useStartAnalysis() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: async ({ request, compounds }: StartAnalysisOptions) => {
      const { analysis_id } = await api.createAnalysis(request)

      if (compounds && compounds.length > 0) {
        const injectResult = await api.injectCompounds(analysis_id, compounds)
        if (injectResult.injected === 0) {
          throw new Error('No valid compounds found. Please check your SMILES/InChI strings.')
        }
      }

      return { analysis_id }
    },
    onSuccess: (data) => {
      localStorage.setItem('hf_last_analysis_id', data.analysis_id)
      navigate(`/analysis/${data.analysis_id}`)
    },
  })
}
