import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useRemoveUserCompound(analysisId: string) {
  const queryClient = useQueryClient()
  return useMutation<{ removed: string }, Error, string>({
    mutationFn: (compoundId) => api.removeUserCompound(analysisId, compoundId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', analysisId] })
    },
  })
}
