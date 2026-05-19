import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function usePlants() {
  return useQuery({
    queryKey: ['plants'],
    queryFn: api.getPlants,
    staleTime: Infinity,
  })
}
