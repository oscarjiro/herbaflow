import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ResetFromRequest } from '@/types/api'

export function useResetFromStage(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ stage, body }: { stage: number; body?: ResetFromRequest }) =>
      api.resetFromStage(id, stage, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', id] })
      queryClient.invalidateQueries({ queryKey: ['analysisStatus', id] })
    },
  })
}
