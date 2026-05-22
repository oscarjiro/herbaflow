import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { isTerminalStatus } from '@/types/api'

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: ['analysis', id],
    queryFn: () => api.getAnalysis(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status || isTerminalStatus(status)) return false
      return 2000
    },
    refetchIntervalInBackground: false,
  })
}
