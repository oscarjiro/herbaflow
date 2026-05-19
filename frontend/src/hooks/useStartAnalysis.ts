import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { CreateAnalysisRequest } from '@/types/api'

export function useStartAnalysis() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (req: CreateAnalysisRequest) => api.createAnalysis(req),
    onSuccess: (data) => {
      localStorage.setItem('hf_last_analysis_id', data.analysis_id)
      navigate(`/analysis/${data.analysis_id}`)
    },
  })
}
