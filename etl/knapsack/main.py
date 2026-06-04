import argparse
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
log = None
REQUEST_DELAY = None
TIMEOUT = None
MAX_RETRIES = None
HEADERS = None


def init_runtime():
    """Build paths, logger, and scraper settings, populating the module-level
    runtime globals. Called from main() — NOT at import — so importing this
    module performs no config read, directory creation, or logging setup."""
    global _cfg, OUTPUT_DIR, PLANTS_CSV, COMPOUNDS_CSV, FAILED_PAGES_LOG
    global log, REQUEST_DELAY, TIMEOUT, MAX_RETRIES, HEADERS

    _cfg = load_settings("knapsack")
    OUTPUT_DIR = ETL_ROOT / _cfg["paths"]["output_dir"]
    PLANTS_CSV = OUTPUT_DIR / _cfg["paths"]["plants_file"]
    COMPOUNDS_CSV = OUTPUT_DIR / _cfg["paths"]["plants_compounds_file"]
    FAILED_PAGES_LOG = OUTPUT_DIR / _cfg["paths"]["failed_pages_log"]

    ensure_dir(OUTPUT_DIR)

    log = setup_logging("knapsack", _cfg)

    REQUEST_DELAY = _cfg["scraper"]["request_delay_seconds"]
    TIMEOUT = _cfg["scraper"]["timeout_seconds"]
    MAX_RETRIES = _cfg["scraper"]["max_retries"]

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


if __name__ == "__main__":
    main()
