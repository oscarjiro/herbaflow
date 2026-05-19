import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: ['analysis', id],
    queryFn: () => api.getAnalysis(id),
    enabled: !!id,
  })
}
