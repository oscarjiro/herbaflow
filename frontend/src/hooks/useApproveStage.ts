import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useApproveStage(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (paramOverrides: Record<string, unknown> | undefined) =>
      api.approveStage(id, paramOverrides ? { param_overrides: paramOverrides } : undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', id] })
    },
  })
}
