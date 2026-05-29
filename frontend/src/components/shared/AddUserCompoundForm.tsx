import { useState } from 'react'
import { useAddUserCompound } from '@/hooks/useAddUserCompound'

interface AddUserCompoundFormProps {
  analysisId: string
}

export function AddUserCompoundForm({ analysisId }: AddUserCompoundFormProps) {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const mutation = useAddUserCompound(analysisId)

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed) return
    setError(null)
    const isInchi = trimmed.startsWith('InChI=')
    try {
      await mutation.mutateAsync(isInchi ? { inchi: trimmed } : { smiles: trimmed })
      setInput('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add compound')
    }
  }

  return (
    <form onSubmit={handleAdd} className="space-y-2">
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="SMILES or InChI string"
          disabled={mutation.isPending}
          className="flex-1 text-xs font-mono bg-hf-bg1 border border-hf-border text-hf-fg2 rounded px-2 py-1.5 focus:outline-none focus:border-hf-fg3 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={mutation.isPending || !input.trim()}
          className="text-xs px-3 py-1.5 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          {mutation.isPending ? 'Validating…' : 'Add'}
        </button>
      </div>
      {error && (
        <p className="text-xs font-sans text-hf-danger">{error}</p>
      )}
    </form>
  )
}
