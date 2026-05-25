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
  { key: 'name',  header: 'Name',  sortable: true },
  { key: 'value', header: 'Value', sortable: true },
]

describe('DataTable', () => {
  it('renders all rows', () => {
    render(<DataTable data={data} columns={columns} />)
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument()
  })

  it('filters rows by text', () => {
    render(<DataTable data={data} columns={columns} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'alp' } })
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.queryByText('Beta')).not.toBeInTheDocument()
    expect(screen.queryByText('Gamma')).not.toBeInTheDocument()
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

  it('shows pagination controls and range when rows exceed page size', () => {
    const bigData = Array.from({ length: 60 }, (_, i) => ({ name: `Item ${i}`, value: i }))
    render(<DataTable data={bigData} columns={columns} pageSize={50} />)
    // Range indicator: first page of 50 shows "1–50 of 60"
    expect(screen.getByText('1–50 of 60')).toBeInTheDocument()
    // Navigation buttons present
    expect(screen.getByLabelText('Previous page')).toBeInTheDocument()
    expect(screen.getByLabelText('Next page')).toBeInTheDocument()
    // Prev disabled on first page, Next enabled
    expect(screen.getByLabelText('Previous page')).toBeDisabled()
    expect(screen.getByLabelText('Next page')).not.toBeDisabled()
  })
})
