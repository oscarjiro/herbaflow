import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useApproveStage(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.approveStage(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', id] })
    },
  })
}
