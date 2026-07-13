import argparse
import concurrent.futures
import csv
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
import pandas as pd
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from requests.adapters import HTTPAdapter
from shared.provenance import knapsack_metabolite_url
from shared.utils import ETL_ROOT, ensure_dir, load_settings, setup_logging
from urllib3.util.retry import Retry

# =========================================================
# CONFIG
# =========================================================
# Cheap, side-effect-free constants stay at module level.
URL = "https://www.knapsackfamily.com/KNApSAcK_World/search.php?cn=IDN&wd=&flg="
BASE_URL = "https://www.knapsackfamily.com/KNApSAcK_World/"

# Runtime state (config, derived paths, logger, scraper settings) is populated
# lazily by init_runtime() — called from main(), never at import — so that
# importing this module has ZERO filesystem side effects.
_cfg = None
OUTPUT_DIR = None
PLANTS_CSV = None
COMPOUNDS_CSV = None
FAILED_PAGES_LOG = None
FAILED_STRUCTURE_PAGES_LOG = None
PAGES_DIR = None
log = None
REQUEST_DELAY = None
TIMEOUT = None
MAX_RETRIES = None
HEADERS = None
STRUCTURE_WORKERS = None


def init_runtime():
    """Build paths, logger, and scraper settings, populating the module-level
    runtime globals. Called from main() — NOT at import — so importing this
    module performs no config read, directory creation, or logging setup."""
    global _cfg, OUTPUT_DIR, PLANTS_CSV, COMPOUNDS_CSV, FAILED_PAGES_LOG
    global FAILED_STRUCTURE_PAGES_LOG, PAGES_DIR
    global log, REQUEST_DELAY, TIMEOUT, MAX_RETRIES, HEADERS, STRUCTURE_WORKERS

    _cfg = load_settings("knapsack")
    OUTPUT_DIR = ETL_ROOT / _cfg["paths"]["output_dir"]
    PLANTS_CSV = OUTPUT_DIR / _cfg["paths"]["plants_file"]
    COMPOUNDS_CSV = OUTPUT_DIR / _cfg["paths"]["plants_compounds_file"]
    FAILED_PAGES_LOG = OUTPUT_DIR / _cfg["paths"]["failed_pages_log"]
    FAILED_STRUCTURE_PAGES_LOG = OUTPUT_DIR / _cfg["paths"]["failed_structure_pages"]
    PAGES_DIR = ETL_ROOT / _cfg["paths"]["knapsack_pages_dir"]

    ensure_dir(OUTPUT_DIR)

    log = setup_logging("knapsack", _cfg)

    REQUEST_DELAY = _cfg["scraper"]["request_delay_seconds"]
    TIMEOUT = _cfg["scraper"]["timeout_seconds"]
    MAX_RETRIES = _cfg["scraper"]["max_retries"]
    STRUCTURE_WORKERS = _cfg["scraper"]["structure_workers"]

    HEADERS = {
        "User-Agent": _cfg["scraper"]["user_agent"]
    }


# ========================================================
# PARSE ARGS
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="KNApSAcK Indonesia Scraper")
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip plants already found in plants_compounds.csv",
    )
    parser.add_argument(
        "--require-detail-url",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only process rows with a detail URL for compound mapping.",
    )
    return parser.parse_args()


# =========================================================
# SESSION WITH RETRIES
# =========================================================
def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# =========================================================
# BASIC HELPERS
# =========================================================
def fetch_soup(session: requests.Session, url: str):
    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        log.error("Failed to fetch %s: %s", url, e)
        return None


def clean_text(value):
    if value is None:
        return None
    text = str(value).replace("\xa0", " ").strip()
    return text if text else None


def cell_text(td, separator=" "):
    if not td:
        return None
    return clean_text(td.get_text(separator=separator, strip=True))


def first_direct_text(td):
    """
    Species cell structure:
    <td>Curcuma longa<a ...><img ...></a><a ...><img ...></a><br></td>
    We want only the plain species text before the icons/links.
    """
    if not td:
        return None

    parts = []
    for child in td.contents:
        if isinstance(child, NavigableString):
            txt = str(child).strip()
            if txt:
                parts.append(txt)
        elif isinstance(child, Tag):
            break

    text = " ".join(parts).strip()
    return text if text else td.get_text(" ", strip=True)


def normalize_url(href: str) -> str:
    if not href:
        return None
    return urljoin(BASE_URL, href)


def write_failed(url: str):
    try:
        with open(FAILED_PAGES_LOG, "a", encoding="utf-8") as f:
            f.write(url + "\n")
    except Exception as e:
        log.error("Failed to write failed URL %s: %s", url, e)


# =========================================================
# TABLE FINDERS
# =========================================================
def find_main_table(soup: BeautifulSoup):
    table = soup.find("table", id="tablekit-table-1")
    if table:
        return table

    for tbl in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True).lower() for th in tbl.find_all("th")]
        if (
            "species name" in headers
            and "purpose" in headers
            and "reference" in headers
        ):
            return tbl

    return None


def find_compound_table(soup: BeautifulSoup):
    all_tables = soup.find_all("table")

    for tbl in all_tables:
        # 1. Check for 'C_ID' or 'Metabolite' in any text inside the table
        header_area = tbl.find_all(["th", "td"])[:12]  # Check the first few cells
        header_text = " ".join([c.get_text().lower() for c in header_area])

        if (
            "c_id" in header_text
            or "metabolite" in header_text
            or "c id" in header_text
        ):
            return tbl

        # 2. Hardcore fallback: Does any cell in the first 3 rows look like a C_ID? (e.g., C00001234)
        for row in tbl.find_all("tr")[:3]:
            if re.search(r"C\d{8}", row.get_text()):
                return tbl

    return None


# =========================================================
# MAIN PAGE SCRAPER
# =========================================================
def extract_detail_url(species_td):
    """
    Find the specific KNApSAcK core link for compound mapping.
    Ignores LunchBox and other irrelevant external links.
    """
    if not species_td:
        return None

    # Preferred: result.php?sname=organism...
    for a in species_td.find_all("a", href=True):
        href = a["href"]
        if "knapsack_core/result.php" in href and "sname=organism" in href:
            return normalize_url(href)

    return None


def scrape_main_page(session: requests.Session, url: str, require_detail_url: bool):
    """
    Scrape medicinal plants from the Indonesia filter page.
    Dedupes by detail_url when available, which is the real unique key.
    """
    plants = []
    seen_detail_urls = set()
    seen_fallback_keys = set()

    plant_counter = 1

    log.info("Scraping main page: %s", url)

    soup = fetch_soup(session, url)
    if not soup:
        write_failed(url)
        return plants

    table = find_main_table(soup)
    if not table:
        log.error("Main table not found on %s", url)
        write_failed(url)
        return plants

    rows = table.find_all("tr")
    for row in rows:
        # If the row contains headers (th), skip it
        if row.find("th"):
            continue

        cols = row.find_all("td")

        # KNApSAcK world has 9 columns
        if len(cols) < 9:
            continue

        species_td = cols[0]
        classification_td = cols[1]
        family_td = cols[2]
        common_td = cols[3]
        purpose_td = cols[4]
        reference_td = cols[8]

        purpose = cell_text(purpose_td)
        if purpose != "medicinal":
            continue

        species_name = first_direct_text(species_td)
        classification = cell_text(classification_td)
        family_name = cell_text(family_td)
        common_name = cell_text(common_td, separator=" | ")
        reference = cell_text(reference_td)

        # Get strict KNApSAcK detail URL
        detail_url = extract_detail_url(species_td)

        # Reject rows that don't have detail_url
        if not detail_url:
            # If detail URL is required, skip immediately
            if require_detail_url:
                log.warning(
                    "Skipping row %d: No detail URL found for species '%s'",
                    plant_counter, species_name,
                )
                continue

            # If detail URL is not required, use fallback key based on row content
            fallback_key = (
                species_name or "",
                classification or "",
                family_name or "",
                common_name or "",
                purpose or "",
                reference or "",
            )
            if fallback_key in seen_fallback_keys:
                log.warning(
                    "Skipping row %d: Fallback key already seen for species '%s'",
                    plant_counter, species_name,
                )
                continue
            seen_fallback_keys.add(fallback_key)

        # Deduplicate by detail_url
        elif detail_url in seen_detail_urls:
            log.warning(
                "Skipping row %d: Detail URL already seen for species '%s'",
                plant_counter, species_name,
            )
            continue
        else:
            seen_detail_urls.add(detail_url)

        # Construct clean record
        plants.append(
            {
                "plant_id": plant_counter,
                "species_name": species_name,
                "family_name": family_name,
                "common_name": common_name,
                "classification": classification,
                "purpose": purpose,
                "reference": reference,
                "detail_url": detail_url,
            }
        )
        plant_counter += 1

    return plants


# =========================================================
# DETAIL / COMPOUNDS SCRAPER
# =========================================================
def scrape_detail_page(session: requests.Session, detail_url: str, plant_id: int):
    """
    Scrape compounds for one unique plant detail page.
    Dedupes compounds inside the page by C_ID, or by row signature if needed.
    """
    compounds = []
    seen_rows = set()

    if not detail_url:
        return compounds

    soup = fetch_soup(session, detail_url)
    if not soup:
        write_failed(detail_url)
        return compounds

    table = find_compound_table(soup)
    if not table:
        log.warning("Compound table not found: %s", detail_url)
        write_failed(detail_url)
        return compounds

    rows = table.find_all("tr")

    for row in rows:
        # If the row contains headers (th), skip it
        if row.find("th"):
            continue

        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        c_id = cell_text(cols[0])
        cas_id = cell_text(cols[1])
        metabolite = cell_text(cols[2])
        molecular_formula = cell_text(cols[3])
        mw = cell_text(cols[4])
        organism = cell_text(cols[5])

        # Prefer dedupe by c_id, which is the stable compound ID.
        # Fallback to full row signature if c_id is missing.
        if c_id:
            row_key = c_id
        else:
            row_key = (cas_id, metabolite, molecular_formula, mw, organism)

        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)

        compounds.append(
            {
                "plant_id": plant_id,
                "c_id": c_id,
                "cas_id": cas_id,
                "metabolite": metabolite,
                "molecular_formula": molecular_formula,
                "mw": mw,
                "organism": organism,
            }
        )

    return compounds


# =========================================================
# STRUCTURE (PHASE 2): InChIKey / SMILES / Formula from the metabolite page
# =========================================================
def parse_structure_page(html: str) -> dict:
    """Parse a KNApSAcK metabolite page for InChIKey / SMILES / Formula.

    Fields are `<tr><th class="inf">Label</th><td>Value</td></tr>` rows in
    `<table class="d3">`. Missing fields come back as "" (never an error).
    """
    out = {"knapsack_inchikey": "", "knapsack_smiles": "", "knapsack_formula": ""}
    soup = BeautifulSoup(html or "", "html.parser")
    label_to_key = {
        "inchikey": "knapsack_inchikey",
        "smiles": "knapsack_smiles",
        "formula": "knapsack_formula",
    }
    for th in soup.find_all("th", class_="inf"):
        label = th.get_text(strip=True).lower()
        key = label_to_key.get(label)
        if not key:
            continue  # skips 'inchicode', 'cas rn', etc.
        td = th.find_next_sibling("td")
        if td is not None:
            out[key] = td.get_text(strip=True)
    return out


def fetch_page_html(session: requests.Session, cid: str) -> str:
    """Return metabolite-page HTML, from the on-disk cache when present.

    Cache hits return immediately with no delay, so a cached re-run stays
    fast. Every real network request is paced by REQUEST_DELAY (win or lose)
    so the STRUCTURE_WORKERS concurrent workers don't burst the server: each
    worker sleeps REQUEST_DELAY between its own requests, so aggregate
    throughput is ~STRUCTURE_WORKERS/REQUEST_DELAY requests/sec.
    """
    cache_path = PAGES_DIR / f"{cid}.html"
    if cache_path.exists() and cache_path.stat().st_size > 200:
        return cache_path.read_text(encoding="utf-8", errors="replace")
    url = knapsack_metabolite_url(cid)
    if not url:
        return ""
    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        html = resp.text
        if len(html) > 200:
            cache_path.write_text(html, encoding="utf-8")
        return html
    except Exception as e:  # noqa: BLE001
        log.error("Structure fetch failed for %s: %s", cid, e)
        return ""
    finally:
        time.sleep(REQUEST_DELAY)


def fetch_structures(c_ids: list[str]) -> dict[str, dict]:
    """Concurrently fetch + parse structure for each unique c_id (cache-backed).

    A c_id whose fetch_page_html returns "" is a genuine fetch failure
    (network exception or empty body), distinct from a page that loaded fine
    but had no structure fields (a legitimate blank parse). Failures are
    written to FAILED_STRUCTURE_PAGES_LOG for a targeted retry pass.
    """
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    failed_cids: list[str] = []

    def _one(cid: str) -> tuple[str, dict, bool]:
        session = make_session()  # requests.Session is not thread-safe; one per task
        html = fetch_page_html(session, cid)
        return cid, parse_structure_page(html), bool(html)

    with concurrent.futures.ThreadPoolExecutor(max_workers=STRUCTURE_WORKERS) as ex:
        for i, (cid, struct, fetched_ok) in enumerate(ex.map(_one, c_ids), start=1):
            results[cid] = struct
            if not fetched_ok:
                failed_cids.append(cid)
            if i % 200 == 0:
                log.info("structure %d/%d", i, len(c_ids))

    log.info(
        "Phase 2: %d/%d structure fetches failed", len(failed_cids), len(c_ids)
    )
    with open(FAILED_STRUCTURE_PAGES_LOG, "w", encoding="utf-8") as f:
        for cid in failed_cids:
            f.write(cid + "\n")

    return results


def attach_structures() -> None:
    """Phase 2: fetch each unique c_id's metabolite page and append the 3
    structure columns to plants_compounds.csv without dropping any existing
    column (the header is read, not hardcoded)."""
    with open(COMPOUNDS_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    c_ids = sorted({r["c_id"].strip() for r in rows if r.get("c_id", "").strip()})
    log.info("Phase 2: fetching structure for %d unique c_ids", len(c_ids))
    structures = fetch_structures(c_ids)

    structure_cols = ["knapsack_inchikey", "knapsack_smiles", "knapsack_formula"]
    fields = fieldnames + [c for c in structure_cols if c not in fieldnames]
    blank_structure = {c: "" for c in structure_cols}

    with open(COMPOUNDS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            r.update(structures.get(r.get("c_id", "").strip(), blank_structure))
            writer.writerow(r)

    log.info("Phase 2 complete: structure columns written to %s", COMPOUNDS_CSV.name)


# =========================================================
# MAIN
# =========================================================
def main():
    init_runtime()
    args = parse_args()
    session = make_session()

    log.info("Scraping medicinal plants from Indonesia filter page...")
    plants = scrape_main_page(session, URL, args.require_detail_url)
    log.info("Found %d unique medicinal plants", len(plants))

    # Save plant discovery results
    df_plants = pd.DataFrame(plants)
    df_plants.to_csv(PLANTS_CSV, index=False, encoding="utf-8-sig")
    log.info("Saved plant list to %s", PLANTS_CSV)

    # Handle checkpoints
    processed_ids = set()
    mode = "a" if (os.path.exists(COMPOUNDS_CSV) and args.resume) else "w"

    if mode == "a":
        try:
            existing_data = pd.read_csv(COMPOUNDS_CSV, usecols=["plant_id"])
            processed_ids = set(existing_data["plant_id"].astype(int).unique())
            log.info("[RESUME] Skipping %d plants already processed.", len(processed_ids))
        except Exception as e:
            log.warning("Could not read existing file, starting fresh: %s", e)
            log.info("[FRESH] Starting a new compounds file.")
            mode = "w"
    else:
        log.info("[FRESH] Starting a new compounds file.")

    with open(COMPOUNDS_CSV, mode, encoding="utf-8-sig", newline="") as f:
        fields = [
            "plant_id",
            "c_id",
            "cas_id",
            "metabolite",
            "molecular_formula",
            "mw",
            "organism",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)

        # Write header if starting fresh or file is new
        if mode == "w":
            writer.writeheader()

        for idx, plant in enumerate(plants, start=1):
            p_id = int(plant["plant_id"])

            # Checkpoint
            if mode == "a" and p_id in processed_ids:
                continue

            try:
                compounds = scrape_detail_page(session, plant["detail_url"], p_id)

                # Write results immediately
                for c in compounds:
                    writer.writerow(c)

                log.info(
                    "[%d/%d] %s: %d compounds",
                    idx, len(plants), plant["species_name"], len(compounds),
                )
                f.flush()

            except Exception as e:
                log.error("Error on %s: %s", plant["detail_url"], e)

            time.sleep(REQUEST_DELAY)

    log.info("Done. Results saved to %s", COMPOUNDS_CSV)
    log.info("Failed pages log: %s", FAILED_PAGES_LOG)

    attach_structures()


if __name__ == "__main__":
    main()
