"""Parse + normalize SwissTargetPrediction result tables into gene-symbol lists.
Pure functions (no I/O); used by the scraper and unit-tested standalone."""
import csv
import io

from app.services import gene_symbols

PROB_COLUMN = "Probability*"
NAME_COLUMN = "Common name"


def parse_stp_csv_text(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _to_float(value: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError:
        return 0.0


def filter_and_normalize(rows: list[dict], min_prob: float = 0.6) -> list[str]:
    """Keep rows with Probability* >= min_prob, map Common name -> canonical gene symbol,
    drop unrecognized, preserve first-seen order, dedup within this molecule."""
    out: list[str] = []
    seen: set[str] = set()
    raw_names = [
        (r.get(NAME_COLUMN) or "").strip()
        for r in rows
        if _to_float(r.get(PROB_COLUMN, "")) >= min_prob and (r.get(NAME_COLUMN) or "").strip()
    ]
    for res in gene_symbols.normalize_many(raw_names):
        if res.status == "unrecognized" or not res.canonical:
            continue
        if res.canonical in seen:
            continue
        seen.add(res.canonical)
        out.append(res.canonical)
    return out


def aggregate_targets(per_molecule: list[list[str]]) -> list[str]:
    """Union across molecules, sorted unique."""
    bag: set[str] = set()
    for genes in per_molecule:
        bag.update(genes)
    return sorted(bag)
