import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useResetFromStage(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (stage: number) => api.resetFromStage(id, stage),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', id] })
    },
  })
}
