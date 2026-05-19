import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useRejectStage(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.rejectStage(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', id] })
    },
  })
}
