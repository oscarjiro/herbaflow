/**
 * SwissTargetPrediction paste-back parser. Keys on real STP header names
 * (Uniprot ID / Common name / Probability), ignores column order, filters by threshold (default 0.6).
 *
 * The real STP export labels the probability column "Probability*" (a trailing asterisk
 * footnote); some hand-trimmed exports drop it. Both spellings are accepted.
 */

export type StpRow = { uniprot: string; common_name: string | null; probability: number };
export type StpParseResult = { rows: StpRow[]; error?: string };

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
  const ui = idx("Uniprot ID");
  if (ui === -1) return { rows: [], error: "Missing required column: Uniprot ID." };
  // Real STP exports the probability column as "Probability*"; tolerate the plain name too.
  const pi = header.findIndex((h) => h === "Probability" || h === "Probability*");
  if (pi === -1) return { rows: [], error: "Missing required column: Probability." };
  const ci = idx("Common name");
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
