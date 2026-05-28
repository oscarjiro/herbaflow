import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { downloadStageExport } from './export'

// ---- DOM mocks ----
const mockClick = vi.fn()
const mockAppendChild = vi.fn()
const mockRemoveChild = vi.fn()
const mockAnchor = {
  href: '',
  download: '',
  click: mockClick,
}

// ---- fetch mock ----
const mockFetch = vi.fn()

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', mockFetch)
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
  vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined)
  vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor as unknown as HTMLAnchorElement)
  vi.spyOn(document.body, 'appendChild').mockImplementation(mockAppendChild)
  vi.spyOn(document.body, 'removeChild').mockImplementation(mockRemoveChild)

  // Default: successful response
  mockFetch.mockResolvedValue({
    ok: true,
    blob: vi.fn().mockResolvedValue(new Blob(['a,b\n1,2'], { type: 'text/csv' })),
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  mockClick.mockClear()
  mockAppendChild.mockClear()
  mockRemoveChild.mockClear()
  mockFetch.mockClear()
  mockAnchor.href = ''
  mockAnchor.download = ''
})

describe('downloadStageExport', () => {
  it('fetches the correct URL with format=csv', async () => {
    await downloadStageExport({ analysisId: 'abc-123', stageNum: 2 })
    expect(mockFetch).toHaveBeenCalledOnce()
    const calledUrl: string = mockFetch.mock.calls[0][0]
    expect(calledUrl).toContain('/api/analyses/abc-123/export/2')
    expect(calledUrl).toContain('format=csv')
  })

  it('includes columns param when provided', async () => {
    await downloadStageExport({
      analysisId: 'abc-123',
      stageNum: 3,
      columns: ['compound_id', 'canonical_name'],
    })
    const calledUrl: string = mockFetch.mock.calls[0][0]
    expect(calledUrl).toContain('columns=compound_id%2Ccanonical_name')
  })

  it('does not include columns param when columns array is empty', async () => {
    await downloadStageExport({ analysisId: 'abc-123', stageNum: 1, columns: [] })
    const calledUrl: string = mockFetch.mock.calls[0][0]
    expect(calledUrl).not.toContain('columns=')
  })

  it('uses correct filename: analysis_{id}_stage{n}.csv', async () => {
    await downloadStageExport({ analysisId: 'my-id', stageNum: 5 })
    expect(mockAnchor.download).toBe('analysis_my-id_stage5.csv')
  })

  it('sets anchor href to the object URL', async () => {
    await downloadStageExport({ analysisId: 'my-id', stageNum: 1 })
    expect(mockAnchor.href).toBe('blob:mock-url')
  })

  it('appends anchor to document body before click', async () => {
    await downloadStageExport({ analysisId: 'my-id', stageNum: 1 })
    expect(mockAppendChild).toHaveBeenCalledWith(mockAnchor)
    expect(mockClick).toHaveBeenCalledOnce()
  })

  it('removes anchor from document body after click', async () => {
    await downloadStageExport({ analysisId: 'my-id', stageNum: 1 })
    expect(mockRemoveChild).toHaveBeenCalledWith(mockAnchor)
  })

  it('revokes object URL after download', async () => {
    await downloadStageExport({ analysisId: 'my-id', stageNum: 1 })
    vi.runAllTimers()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
  })

  it('throws when response is not ok', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 404, statusText: 'Not Found' })
    await expect(
      downloadStageExport({ analysisId: 'bad-id', stageNum: 99 })
    ).rejects.toThrow('Export failed: 404 Not Found')
  })

  it('includes metadata param when includeMetadata is true', async () => {
    await downloadStageExport({ analysisId: 'abc', stageNum: 1, includeMetadata: true })
    const calledUrl: string = mockFetch.mock.calls[0][0]
    expect(calledUrl).toContain('metadata=true')
  })

  it('includes headers=false param when includeHeaders is false', async () => {
    await downloadStageExport({ analysisId: 'abc', stageNum: 1, includeHeaders: false })
    const calledUrl: string = mockFetch.mock.calls[0][0]
    expect(calledUrl).toContain('headers=false')
  })

  it('does not include headers param when includeHeaders is true (default)', async () => {
    await downloadStageExport({ analysisId: 'abc', stageNum: 1, includeHeaders: true })
    const calledUrl: string = mockFetch.mock.calls[0][0]
    expect(calledUrl).not.toContain('headers=')
  })
})
