import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { AddUserCompoundRequest, AddUserCompoundResponse } from '@/types/api'

export function useAddUserCompound(analysisId: string) {
  const queryClient = useQueryClient()
  return useMutation<AddUserCompoundResponse, Error, AddUserCompoundRequest>({
    mutationFn: (body) => api.addUserCompound(analysisId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis', analysisId] })
    },
  })
}
