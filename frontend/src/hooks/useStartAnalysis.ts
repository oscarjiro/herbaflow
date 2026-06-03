import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { CreateAnalysisRequest } from '@/types/api'

export interface StartAnalysisOptions {
  request: CreateAnalysisRequest
}

export function useStartAnalysis() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: async ({ request }: StartAnalysisOptions) => {
      const { analysis_id } = await api.createAnalysis(request)
      return { analysis_id }
    },
    onSuccess: (data) => {
      localStorage.setItem('hf_last_analysis_id', data.analysis_id)
      navigate(`/analysis/${data.analysis_id}`)
    },
  })
}
