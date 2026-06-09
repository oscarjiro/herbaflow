/**
 * SwissTargetPrediction paste-back parser. Keys strictly on real STP header names
 * (Uniprot ID / Common name / Probability), ignores column order, filters by threshold (default 0.6).
 */

export type StpRow = { uniprot: string; common_name: string | null; probability: number };
export type StpParseResult = { rows: StpRow[]; error?: string };

const REQUIRED = ["Uniprot ID", "Probability"] as const;

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQ && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else inQ = !inQ;
    } else if (ch === "," && !inQ) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

export function parseStpCsv(text: string, threshold = 0.6): StpParseResult {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return { rows: [], error: "Empty CSV." };
  const header = splitCsvLine(lines[0]!);
  const idx = (name: string) => header.indexOf(name);
  for (const col of REQUIRED) {
    if (idx(col) === -1) return { rows: [], error: `Missing required column: ${col}.` };
  }
  const ui = idx("Uniprot ID");
  const ci = idx("Common name");
  const pi = idx("Probability");
  const rows: StpRow[] = [];
  for (const line of lines.slice(1)) {
    const cells = splitCsvLine(line);
    const probability = Number(cells[pi] ?? "");
    if (!Number.isFinite(probability) || probability < threshold) continue;
    const uniprot = (cells[ui] ?? "").toUpperCase();
    if (!/^[A-Z0-9]{6,10}$/.test(uniprot)) continue;
    rows.push({ uniprot, common_name: ci === -1 ? null : cells[ci] || null, probability });
  }
  return { rows };
}
