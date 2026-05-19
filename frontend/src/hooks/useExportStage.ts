import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useExportStage() {
  return useMutation({
    mutationFn: async ({ id, stage, format }: { id: string; stage: number; format: 'csv' | 'json' }) => {
      const res = await api.exportStage(id, stage, format)
      if (!res.ok) throw new Error(`Export failed: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `analysis_${id}_stage${stage}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    },
  })
}
