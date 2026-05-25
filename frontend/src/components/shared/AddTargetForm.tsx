// frontend/src/components/shared/AddTargetForm.tsx
import { useState } from 'react'

interface AddTargetFormProps {
  onSubmit: (input: string) => Promise<void>
  loading: boolean
  error: string | null
  placeholder?: string
}

export function AddTargetForm({
  onSubmit,
  loading,
  error,
  placeholder = 'Gene symbol or UniProt accession',
}: AddTargetFormProps) {
  const [value, setValue] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!value.trim()) return
    await onSubmit(value.trim())
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          disabled={loading}
          className="flex-1 text-xs font-mono bg-hf-bg1 border border-hf-border text-hf-fg2 rounded px-2 py-1.5 focus:outline-none focus:border-hf-fg3 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="text-xs px-3 py-1.5 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          {loading ? 'Validating…' : 'Add'}
        </button>
      </div>
      {error && (
        <p className="text-xs font-sans text-hf-terracotta">{error}</p>
      )}
    </form>
  )
}
