import type { UncoveredCompound, STPTargetImport } from '@/types/api'

export interface ParsedSTPResult {
  targets: STPTargetImport[]
  error: string | null
}

/**
 * Parse a SwissTargetPrediction result CSV/TSV.
 *
 * Expected columns (case-insensitive): Uniprot, Gene name, Probability.
 * Handles both comma and tab separators. Rows with probability < minProbability
 * are excluded.
 *
 * Returns { targets, error: null } on success, { targets: [], error: string } on failure.
 */
export function parseSTPCsv(text: string, minProbability: number): ParsedSTPResult {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length < 2) {
    return { targets: [], error: 'File appears empty — expected header row plus at least one data row' }
  }

  // Auto-detect separator: prefer tab, fall back to comma
  const separator = lines[0].includes('\t') ? '\t' : ','
  const header = lines[0].split(separator).map(h => h.trim().replace(/"/g, '').toLowerCase())

  const uniprotIdx = header.findIndex(h => h === 'uniprot')
  const geneIdx = header.findIndex(h => h === 'gene name' || h === 'gene_name')
  const probIdx = header.findIndex(h => h === 'probability')

  if (uniprotIdx === -1 || geneIdx === -1 || probIdx === -1) {
    return {
      targets: [],
      error: 'Unrecognized format — expected columns: Uniprot, Gene name, Probability',
    }
  }

  const targets: STPTargetImport[] = []
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue
    const cols = line.split(separator).map(c => c.trim().replace(/"/g, ''))
    const prob = parseFloat(cols[probIdx] ?? '')
    if (isNaN(prob) || prob < minProbability) continue
    const uniprot = cols[uniprotIdx]?.trim()
    if (!uniprot) continue
    targets.push({
      uniprot_id: uniprot,
      gene_symbol: cols[geneIdx]?.trim() ?? '',
      probability: prob,
    })
  }

  return { targets, error: null }
}

/**
 * Generate a CSV for uncovered compounds to use as STP input.
 *
 * Columns: compound_name, smiles
 * Compounds without a SMILES string are excluded (STP requires SMILES).
 * Double-quotes in names are escaped per RFC 4180.
 */
export function generateSTPExportCsv(compounds: UncoveredCompound[]): string {
  const rows = [
    'compound_name,smiles',
    ...compounds
      .filter(c => c.smiles !== null && c.smiles !== undefined)
      .map(c => `"${c.canonical_name.replace(/"/g, '""')}","${c.smiles}"`),
  ]
  return rows.join('\n')
}
