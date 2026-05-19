import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useDiseases() {
  return useQuery({
    queryKey: ['diseases'],
    queryFn: api.getDiseases,
    staleTime: Infinity,
  })
}
