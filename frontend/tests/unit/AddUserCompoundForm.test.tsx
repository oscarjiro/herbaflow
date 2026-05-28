import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { AddUserCompoundForm } from '@/components/shared/AddUserCompoundForm'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

function renderForm(analysisId = 'test-analysis-id') {
  return render(
    React.createElement(AddUserCompoundForm, { analysisId }),
    { wrapper: makeWrapper() }
  )
}

describe('AddUserCompoundForm', () => {
  beforeEach(() => {
    server.use(
      http.post('http://localhost:8000/analyses/:id/user-compounds', () =>
        HttpResponse.json({
          compound_id: 'cmp-123',
          canonical_name: 'Test Compound',
          smiles: 'CCO',
        })
      )
    )
  })

  it('renders the SMILES/InChI text input and Add button', () => {
    renderForm()
    expect(screen.getByPlaceholderText('SMILES or InChI string')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument()
  })

  it('disables submit button when input is empty', () => {
    renderForm()
    expect(screen.getByRole('button', { name: 'Add' })).toBeDisabled()
  })

  it('enables submit button when input has text', () => {
    renderForm()
    const input = screen.getByPlaceholderText('SMILES or InChI string')
    fireEvent.change(input, { target: { value: 'CCO' } })
    expect(screen.getByRole('button', { name: 'Add' })).not.toBeDisabled()
  })

  it('does not show error initially', () => {
    renderForm()
    // No error paragraph on initial render
    expect(screen.queryByText(/Failed to add compound/)).not.toBeInTheDocument()
  })

  it('submitting with valid SMILES calls mutation and clears input on success', async () => {
    renderForm()
    const input = screen.getByPlaceholderText('SMILES or InChI string')
    fireEvent.change(input, { target: { value: 'CCO' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Add' }).closest('form')!)
    await waitFor(() => {
      expect((input as HTMLInputElement).value).toBe('')
    })
  })

  it('shows error message when mutation fails', async () => {
    server.use(
      http.post('http://localhost:8000/analyses/:id/user-compounds', () =>
        HttpResponse.json({ detail: 'Invalid SMILES string' }, { status: 400 })
      )
    )
    renderForm()
    const input = screen.getByPlaceholderText('SMILES or InChI string')
    fireEvent.change(input, { target: { value: 'INVALID' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Add' }).closest('form')!)
    await waitFor(() => {
      expect(screen.getByText(/Invalid SMILES string/)).toBeInTheDocument()
    })
  })

  it('disables submit button while mutation is pending', async () => {
    // Use a slow response to catch the pending state
    server.use(
      http.post('http://localhost:8000/analyses/:id/user-compounds', async () => {
        await new Promise(resolve => setTimeout(resolve, 100))
        return HttpResponse.json({ compound_id: 'c1', canonical_name: 'Test', smiles: null })
      })
    )
    renderForm()
    const input = screen.getByPlaceholderText('SMILES or InChI string')
    fireEvent.change(input, { target: { value: 'CCO' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Add' }).closest('form')!)
    // Button should show "Validating…" while pending
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Validating…' })).toBeDisabled()
    })
  })

  it('sends inchi field when input starts with InChI=', async () => {
    let capturedBody: unknown = null
    server.use(
      http.post('http://localhost:8000/analyses/:id/user-compounds', async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ compound_id: 'c1', canonical_name: 'Test', smiles: null })
      })
    )
    renderForm()
    const input = screen.getByPlaceholderText('SMILES or InChI string')
    fireEvent.change(input, { target: { value: 'InChI=1S/CH4/h1H4' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Add' }).closest('form')!)
    await waitFor(() => {
      expect(capturedBody).toEqual({ inchi: 'InChI=1S/CH4/h1H4' })
    })
  })

  it('sends smiles field when input does not start with InChI=', async () => {
    let capturedBody: unknown = null
    server.use(
      http.post('http://localhost:8000/analyses/:id/user-compounds', async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ compound_id: 'c1', canonical_name: 'Test', smiles: 'CCO' })
      })
    )
    renderForm()
    const input = screen.getByPlaceholderText('SMILES or InChI string')
    fireEvent.change(input, { target: { value: 'CCO' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Add' }).closest('form')!)
    await waitFor(() => {
      expect(capturedBody).toEqual({ smiles: 'CCO' })
    })
  })
})
