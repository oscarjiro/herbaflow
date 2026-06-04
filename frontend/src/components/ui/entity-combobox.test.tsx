// entity-combobox.test.tsx
// jsdom shims required by Radix Popover + cmdk in jsdom
Element.prototype.hasPointerCapture = vi.fn() as unknown as typeof Element.prototype.hasPointerCapture
Element.prototype.scrollIntoView = vi.fn()
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EntityCombobox } from './entity-combobox'

interface Row { id: string; name: string }
const items: Row[] = [
  { id: '1', name: 'Curcuma longa' },
  { id: '2', name: 'Zingiber officinale' },
]

function setup(value: string[] = []) {
  const onChange = vi.fn()
  render(
    <EntityCombobox<Row>
      multi
      items={items}
      value={value}
      onChange={onChange}
      getKey={(r) => r.id}
      getLabel={(r) => r.name}
      searchKeys={[{ name: 'name', weight: 1 }]}
      placeholder="Select plants..."
      triggerLabel={(n) => (n === 0 ? 'Select plants...' : `${n} selected`)}
      renderRow={(r) => <span>{r.name}</span>}
    />,
  )
  return { onChange }
}

describe('EntityCombobox', () => {
  it('toggles selection on click', async () => {
    const { onChange } = setup([])
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(screen.getByText('Curcuma longa'))
    expect(onChange).toHaveBeenCalledWith(['1'])
  })

  it('pins selected items at the top of the list', async () => {
    setup(['2']) // Zingiber selected
    await userEvent.click(screen.getByRole('combobox'))
    const options = screen.getAllByRole('option')
    expect(options[0]).toHaveTextContent('Zingiber officinale')
  })

  it('disables rows matched by disabledKey and ignores clicks on them', async () => {
    const onChange = vi.fn()
    render(
      <EntityCombobox<Row>
        multi
        items={items}
        value={[]}
        onChange={onChange}
        getKey={(r) => r.id}
        getLabel={(r) => r.name}
        searchKeys={[{ name: 'name', weight: 1 }]}
        placeholder="Select plants..."
        triggerLabel={(n) => (n === 0 ? 'Select plants...' : `${n} selected`)}
        renderRow={(r) => <span>{r.name}</span>}
        disabledKey={(r) => r.id === '1'}
      />,
    )
    await userEvent.click(screen.getByRole('combobox'))
    const disabledRow = screen.getByText('Curcuma longa').closest('[role="option"]')
    expect(disabledRow).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(screen.getByText('Curcuma longa'))
    expect(onChange).not.toHaveBeenCalled()
  })
})
