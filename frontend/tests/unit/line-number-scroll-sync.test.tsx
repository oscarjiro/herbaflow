/**
 * Unit tests for line-number scroll sync in SetupPage textarea sections.
 * The line-number column must scroll in sync with its paired textarea.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

async function renderSetupPage() {
  const { default: SetupPage } = await import('@/pages/SetupPage')
  const queryClient = makeQueryClient()
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SetupPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('SetupPage — line numbers scroll in sync with textarea', () => {
  it('line numbers scroll in sync with the compounds textarea', async () => {
    await renderSetupPage()

    // Switch to manual compounds mode to reveal the textarea
    const manualBtn = screen.getByTestId('input-mode-manual')
    fireEvent.click(manualBtn)

    const textarea = screen.getByTestId('compounds-textarea')
    const lineNums = screen.getByTestId('compounds-line-nums')

    // Simulate the user scrolling the textarea
    Object.defineProperty(textarea, 'scrollTop', { writable: true, value: 120 })
    fireEvent.scroll(textarea)

    // The line-number column's scrollTop must match the textarea
    expect(lineNums.scrollTop).toBe(120)
  })

  it('line numbers scroll in sync with the targets textarea', async () => {
    await renderSetupPage()

    // Switch to manual targets mode to reveal the targets textarea
    const manualTargetsBtn = screen.getByTestId('input-mode-manual-targets')
    fireEvent.click(manualTargetsBtn)

    const textarea = screen.getByTestId('targets-textarea')
    const lineNums = screen.getByTestId('targets-line-nums')

    Object.defineProperty(textarea, 'scrollTop', { writable: true, value: 80 })
    fireEvent.scroll(textarea)

    expect(lineNums.scrollTop).toBe(80)
  })
})
