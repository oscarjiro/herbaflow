import * as React from 'react'
import Fuse from 'fuse.js'
import { Check, ChevronsUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface EntityComboboxProps<T> {
  items: T[]
  value: string[]                 // selected keys (length 0/1 for single)
  onChange: (keys: string[]) => void
  getKey: (item: T) => string
  getLabel: (item: T) => string
  renderRow: (item: T) => React.ReactNode
  searchKeys: { name: string; weight?: number }[]
  placeholder: string
  triggerLabel: (selectedCount: number) => string
  multi?: boolean
  isLoading?: boolean
  disabledKey?: (item: T) => boolean
}

export function EntityCombobox<T>(p: EntityComboboxProps<T>) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')
  React.useEffect(() => { if (!open) setQuery('') }, [open])

  const fuse = React.useMemo(
    () => new Fuse(p.items, { keys: p.searchKeys, threshold: 0.4, includeScore: true }),
    [p.items, p.searchKeys],
  )
  const filtered = React.useMemo(
    () => (query.trim() ? fuse.search(query).map((r) => r.item) : p.items),
    [fuse, query, p.items],
  )
  // Selected-at-top: stable partition of the filtered list.
  const ordered = React.useMemo(() => {
    const sel = new Set(p.value)
    const selected = filtered.filter((i) => sel.has(p.getKey(i)))
    const rest = filtered.filter((i) => !sel.has(p.getKey(i)))
    return [...selected, ...rest]
  }, [filtered, p.value, p])

  function toggle(key: string) {
    if (p.multi) {
      p.onChange(p.value.includes(key) ? p.value.filter((k) => k !== key) : [...p.value, key])
    } else {
      p.onChange(p.value[0] === key ? [] : [key])
      setOpen(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-expanded={open}
          className="w-full justify-between rounded-sm border-hf-border bg-hf-surface text-hf-fg2">
          <span className={p.value.length === 0 ? 'text-hf-fg3' : undefined}>
            {p.value.length === 0 ? p.placeholder : p.triggerLabel(p.value.length)}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput placeholder={p.placeholder} value={query} onValueChange={setQuery} />
          <CommandList className="max-h-64">
            {p.isLoading && <CommandEmpty>Loading…</CommandEmpty>}
            {!p.isLoading && ordered.length === 0 && <CommandEmpty>No results.</CommandEmpty>}
            {!p.isLoading && ordered.length > 0 && (
              <CommandGroup>
                {ordered.map((item) => {
                  const key = p.getKey(item)
                  const selected = p.value.includes(key)
                  const disabled = p.disabledKey?.(item) ?? false
                  return (
                    <CommandItem
                      key={key}
                      value={key}
                      role="option"
                      disabled={disabled}
                      onSelect={() => { if (!disabled) toggle(key) }}
                    >
                      <Check className={cn('mr-2 h-4 w-4 shrink-0', selected ? 'opacity-100' : 'opacity-0')} />
                      {p.renderRow(item)}
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
