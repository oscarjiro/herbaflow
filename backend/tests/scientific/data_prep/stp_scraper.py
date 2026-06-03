"""One-time SwissTargetPrediction scraper (NON-CI). Submits each SMILES, waits for the
job, reads the full results table, and returns its text for stp_parse. Gentle by design.

Prereq:  cd backend && uv sync --extra stp && uv run playwright install chromium
Run:     cd backend && uv run python -m tests.scientific.data_prep.stp_scraper \
             --in tests/scientific/data_prep/_smiles/curcuma_screened_smiles.csv \
             --out tests/scientific/fixtures/curcuma_longa_stp_targets.csv

Selectors captured during live recon (Task A3, 2026-06-03; STP post-2026-05-15 ChemAxon
removal). The May-15 change did NOT alter the result-table schema — column headers are
still "Common name" and "Probability*", so stp_parse's constants remain valid.
  organism radio:   input[name='organism'][value='Homo_sapiens']  (checked by default)
  SMILES textbox:   #smilesBox      (name='smiles', <input type=text>)
  submit button:    #submitButton   (JS button; POSTs #myForm -> /predict.php)
  results URL:      result.php?job=<id>&organism=Homo_sapiens
  results table:    #resultTable  (jQuery DataTables; "Common name"=col 1, "Probability*"=col 5)
  pagination:       DataTables defaults to 15 rows/page of N total; the length <select
                    name='resultTable_length'> offers value "-1" (=All). We MUST select All
                    before reading the DOM, otherwise only the first 15 of (up to ~100) rows
                    are present. (We read the DOM rather than the DataTables CSV-export button
                    to avoid headless download-handler flakiness; All-rows is the same set.)
"""
import argparse
import csv
import time

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from tests.scientific.data_prep.stp_parse import (
    aggregate_targets,
    filter_and_normalize,
    parse_stp_csv_text,
)

STP_URL = "https://www.swisstargetprediction.ch/"
POLITE_DELAY_S = 5.0          # between molecules — respect the free academic service
JOB_TIMEOUT_MS = 120_000      # STP states calculations can take up to ~1 minute

# DOM extraction: pull (Common name, Probability*) from every result row. Returns a list of
# {name, prob} objects so we can rebuild a minimal CSV for the unit-tested parser.
_EXTRACT_ROWS_JS = """
trs => trs.map(tr => {
  const td = tr.querySelectorAll('td');
  return { name: (td[1] && td[1].textContent.trim()) || '',
           prob: (td[5] && td[5].textContent.trim()) || '' };
})
"""


def _read_smiles(path: str) -> list[tuple[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [(row["canonical_name"], row["smiles"]) for row in csv.DictReader(fh)]


def _rows_to_csv_text(rows: list[dict]) -> str:
    """Rebuild a minimal STP-shaped CSV (only the columns stp_parse needs)."""
    out_lines = ["Common name,Probability*"]
    for r in rows:
        name = (r.get("name") or "").replace(",", " ").strip()
        prob = (r.get("prob") or "").strip()
        if name:
            out_lines.append(f"{name},{prob}")
    return "\n".join(out_lines) + "\n"


def _scrape_one(page, smiles: str) -> str:
    """Submit one SMILES; return result-table text (CSV) for stp_parse. Selectors per A3 recon."""
    page.goto(STP_URL, wait_until="domcontentloaded")
    page.check("input[name='organism'][value='Homo_sapiens']")
    page.fill("#smilesBox", smiles)
    # #submitButton is disabled until the box's key handler fires; fill() alone doesn't
    # trigger it. Nudge the handler, then click; fall back to the page's own submit fn
    # (the button's onclick is formSubmit()).
    for ev in ("input", "keyup", "change"):
        page.dispatch_event("#smilesBox", ev)
    try:
        page.wait_for_selector("#submitButton:not([disabled])", timeout=5000)
        page.click("#submitButton")
    except PWTimeout:
        page.evaluate("formSubmit()")
    # Results page (job is calculated server-side; can take up to ~1 min).
    page.wait_for_url("**/result.php**", timeout=JOB_TIMEOUT_MS)
    page.wait_for_selector("#resultTable tbody tr", timeout=JOB_TIMEOUT_MS)
    # Show every row before reading (DataTables paginates at 15).
    try:
        page.select_option("select[name='resultTable_length']", "-1")
        page.wait_for_timeout(500)  # let DataTables re-render all rows
    except PWTimeout:
        pass
    rows = page.eval_on_selector_all("#resultTable tbody tr", _EXTRACT_ROWS_JS)
    return _rows_to_csv_text(rows)


def scrape(in_path: str, out_path: str, min_prob: float = 0.6) -> None:
    smiles_rows = _read_smiles(in_path)
    per_molecule: list[list[str]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        for i, (name, smiles) in enumerate(smiles_rows, 1):
            try:
                csv_text = _scrape_one(page, smiles)
                genes = filter_and_normalize(parse_stp_csv_text(csv_text), min_prob=min_prob)
                per_molecule.append(genes)
                print(f"[{i}/{len(smiles_rows)}] {name}: {len(genes)} targets", flush=True)
            except Exception as exc:  # keep going; log the miss, don't lose the batch
                print(f"[{i}/{len(smiles_rows)}] {name}: ERROR {exc}", flush=True)
                per_molecule.append([])
            time.sleep(POLITE_DELAY_S)
        browser.close()
    agg = aggregate_targets(per_molecule)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["gene_symbol"])
        for g in agg:
            w.writerow([g])
    print(f"wrote {len(agg)} unique gene symbols -> {out_path}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--min-prob", type=float, default=0.6)
    args = ap.parse_args()
    scrape(args.in_path, args.out_path, min_prob=args.min_prob)
