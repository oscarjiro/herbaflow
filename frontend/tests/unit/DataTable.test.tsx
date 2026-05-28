import { render, screen, fireEvent } from '@testing-library/react'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'

const data = [
  { name: 'Alpha', value: 30 },
  { name: 'Beta',  value: 10 },
  { name: 'Gamma', value: 20 },
]

type Row = typeof data[number]

const columns: ColumnDef<Row>[] = [
  { key: 'name',  header: 'Name',  sortable: true, enableColumnFilter: true },
  { key: 'value', header: 'Value', sortable: true, enableColumnFilter: true },
]

describe('DataTable', () => {
  it('renders all rows', () => {
    render(<DataTable data={data} columns={columns} />)
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument()
  })

  it('filters rows by column when filterable={true}', () => {
    render(<DataTable data={data} columns={columns} filterable={true} />)
    // Target the per-column Name filter input specifically
    const nameFilterInput = screen.getByLabelText('Filter name')
    fireEvent.change(nameFilterInput, { target: { value: 'alp' } })
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.queryByText('Beta')).not.toBeInTheDocument()
    expect(screen.queryByText('Gamma')).not.toBeInTheDocument()
  })

  it('does not show filter inputs when filterable is not set', () => {
    render(<DataTable data={data} columns={columns} />)
    expect(screen.queryByLabelText('Filter name')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Filter value')).not.toBeInTheDocument()
  })

  it('shows per-column filter inputs when filterable={true}', () => {
    render(<DataTable data={data} columns={columns} filterable={true} />)
    expect(screen.getByLabelText('Filter name')).toBeInTheDocument()
    expect(screen.getByLabelText('Filter value')).toBeInTheDocument()
  })

  it('sorts asc then desc on column click', () => {
    render(<DataTable data={data} columns={columns} />)
    const valueHeader = screen.getByText('Value')
    fireEvent.click(valueHeader)
    // After asc sort: Beta(10), Gamma(20), Alpha(30)
    const cells = screen.getAllByRole('cell')
    const names = cells.filter((_, i) => i % 2 === 0).map(c => c.textContent)
    expect(names).toEqual(['Beta', 'Gamma', 'Alpha'])

    fireEvent.click(valueHeader)
    // After desc sort: Alpha(30), Gamma(20), Beta(10)
    const cells2 = screen.getAllByRole('cell')
    const names2 = cells2.filter((_, i) => i % 2 === 0).map(c => c.textContent)
    expect(names2).toEqual(['Alpha', 'Gamma', 'Beta'])
  })

  it('disables all sorting when sortable={false}', () => {
    render(<DataTable data={data} columns={columns} sortable={false} />)
    const nameHeader = screen.getByText('Name')
    fireEvent.click(nameHeader)
    // Sort indicator should NOT appear
    expect(nameHeader.closest('th')?.querySelector('[data-sort-indicator]')).toBeNull()
  })

  it('shows Page X of Y pagination label when rows exceed page size', () => {
    const bigData = Array.from({ length: 60 }, (_, i) => ({ name: `Item ${i}`, value: i }))
    render(<DataTable data={bigData} columns={columns} pageSize={50} />)
    // Page label: "Page 1 of 2"
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    // Navigation buttons present
    expect(screen.getByLabelText('Previous page')).toBeInTheDocument()
    expect(screen.getByLabelText('Next page')).toBeInTheDocument()
    // Prev disabled on first page, Next enabled
    expect(screen.getByLabelText('Previous page')).toBeDisabled()
    expect(screen.getByLabelText('Next page')).not.toBeDisabled()
  })

  // ---- TDD tests for TanStack Table v8 upgrade ----

  it('renders column headers', () => {
    render(<DataTable data={data} columns={columns} />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Value')).toBeInTheDocument()
  })

  it('shows sort indicator after clicking a sortable column header', () => {
    render(<DataTable data={data} columns={columns} />)
    const nameHeader = screen.getByText('Name')
    // Before clicking: no sort indicator on Name
    expect(nameHeader.closest('th')?.querySelector('[data-sort-indicator]')).toBeNull()
    fireEvent.click(nameHeader)
    // After one click: ascending sort indicator visible
    const th = nameHeader.closest('th')
    expect(th?.querySelector('[data-sort-indicator]')).not.toBeNull()
    expect(th?.textContent).toMatch(/↑/)
  })

  it('shows descending indicator on second click and resets on third', () => {
    render(<DataTable data={data} columns={columns} />)
    const nameHeader = screen.getByText('Name')
    fireEvent.click(nameHeader) // asc
    expect(nameHeader.closest('th')?.textContent).toMatch(/↑/)
    fireEvent.click(nameHeader) // desc
    expect(nameHeader.closest('th')?.textContent).toMatch(/↓/)
    fireEvent.click(nameHeader) // reset
    const th = nameHeader.closest('th')
    expect(th?.querySelector('[data-sort-indicator]')).toBeNull()
  })

  it('renders all rows and no pagination UI when pageSize is not provided', () => {
    render(<DataTable data={data} columns={columns} />)
    const rows = screen.getAllByRole('row')
    // 1 header row + 3 data rows
    expect(rows).toHaveLength(4)
    // No pagination controls
    expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument()
    expect(screen.queryByText(/^Page \d+ of \d+$/)).not.toBeInTheDocument()
  })

  it('shows only pageSize rows when pageSize is set', () => {
    const bigData = Array.from({ length: 15 }, (_, i) => ({ name: `Item ${i}`, value: i }))
    render(<DataTable data={bigData} columns={columns} pageSize={10} />)
    const rows = screen.getAllByRole('row')
    // 1 header + 10 data rows
    expect(rows).toHaveLength(11)
  })

  it('navigates to next page when Next is clicked', () => {
    const bigData = Array.from({ length: 15 }, (_, i) => ({ name: `Item ${i}`, value: i }))
    render(<DataTable data={bigData} columns={columns} pageSize={10} />)
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Next page'))
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
    // Next should now be disabled (last page), Prev enabled
    expect(screen.getByLabelText('Next page')).toBeDisabled()
    expect(screen.getByLabelText('Previous page')).not.toBeDisabled()
  })

  it('navigates back with Previous button', () => {
    const bigData = Array.from({ length: 15 }, (_, i) => ({ name: `Item ${i}`, value: i }))
    render(<DataTable data={bigData} columns={columns} pageSize={10} />)
    fireEvent.click(screen.getByLabelText('Next page'))
    fireEvent.click(screen.getByLabelText('Previous page'))
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
  })

  it('renders custom cell content via render function', () => {
    const withRender: ColumnDef<Row>[] = [
      { key: 'name', header: 'Name', render: (v) => <span data-testid="custom">{String(v)}-custom</span> },
      { key: 'value', header: 'Value' },
    ]
    render(<DataTable data={[{ name: 'Alpha', value: 30 }]} columns={withRender} />)
    expect(screen.getByTestId('custom')).toHaveTextContent('Alpha-custom')
  })

  it('applies rowClassName to data rows', () => {
    render(
      <DataTable
        data={data}
        columns={columns}
        rowClassName={(row) => row.value > 20 ? 'highlighted' : ''}
      />
    )
    const rows = screen.getAllByRole('row')
    // find the row with Alpha
    const alphaRowEl = rows.find(r => r.textContent?.includes('Alpha'))
    expect(alphaRowEl?.className).toContain('highlighted')
  })

  it('renders "No results" text when data is empty', () => {
    render(<DataTable data={[]} columns={columns} />)
    expect(screen.getByText('No results')).toBeInTheDocument()
  })
})
