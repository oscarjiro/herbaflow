import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import NotFoundPage from '@/pages/NotFoundPage'

// Regression: App.tsx must have a catch-all `<Route path="*">` inside the layout
// route, otherwise an unmatched URL (deep link or typo) renders a blank page
// inside the chrome. This mirrors the route tree declared in App.tsx.

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<div>home</div>} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

describe('catch-all route', () => {
  it('renders the NotFound page for an unknown URL', () => {
    renderAt('/this-route-does-not-exist')
    expect(screen.getByText('404')).toBeInTheDocument()
    expect(screen.getByText(/page not found/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to home/i })).toBeInTheDocument()
  })

  it('does not render NotFound for a matched route', () => {
    renderAt('/')
    expect(screen.queryByText('404')).not.toBeInTheDocument()
  })
})
