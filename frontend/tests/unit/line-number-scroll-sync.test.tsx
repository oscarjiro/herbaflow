/**
 * Unit tests for line-number scroll sync in SetupPage textarea sections.
 * The line-number column must scroll in sync with its paired textarea.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SetupPage from '@/pages/SetupPage'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

function renderSetupPage() {
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
  it('line numbers scroll in sync with the compounds textarea', () => {
    renderSetupPage()

    // Switch to manual compounds mode to reveal the textarea
    const manualBtn = screen.getByTestId('input-mode-manual')
    fireEvent.click(manualBtn)

    const textarea = screen.getByLabelText('Compounds')
    const lineNums = screen.getByTestId('line-nums')

    // Simulate the user scrolling the textarea
    // Use configurable: true to allow jsdom to read the scrollTop value
    Object.defineProperty(textarea, 'scrollTop', {
      configurable: true,
      get: () => 120,
    })
    fireEvent.scroll(textarea)

    // The line-number column's scrollTop must match the textarea
    expect(lineNums.scrollTop).toBe(120)
  })

  it('line numbers scroll in sync with the targets textarea', () => {
    renderSetupPage()

    // Switch to manual targets mode to reveal the targets textarea
    const manualTargetsBtn = screen.getByTestId('input-mode-manual-targets')
    fireEvent.click(manualTargetsBtn)

    const textarea = screen.getByLabelText('Targets')
    const lineNums = screen.getByTestId('line-nums')

    // Use configurable: true to allow jsdom to read the scrollTop value
    Object.defineProperty(textarea, 'scrollTop', {
      configurable: true,
      get: () => 80,
    })
    fireEvent.scroll(textarea)

    expect(lineNums.scrollTop).toBe(80)
  })
})
