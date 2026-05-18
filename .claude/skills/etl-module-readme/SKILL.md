---
name: etl-module-readme
description: Use when creating or updating a README.md for a Herbaflow ETL pipeline module. Covers required sections, academic framing for network pharmacology context, schema tables, configuration reference, and operational instructions.
---

# ETL Module README

## Overview

Each Herbaflow ETL module needs a README that serves dual purpose: operational reference for running the pipeline AND academic documentation suitable for citing in a network pharmacology research report. Write for both audiences simultaneously.

## Required Sections (in order)

### 1. Module Title + One-liner

Name + single sentence: what the module fetches and what tables it produces.

### 2. Purpose in the NP Workflow

2–3 paragraphs. Explain where this module sits in the pipeline chain (`knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/`), what biological question it answers, and how its outputs feed the downstream overlap/PPI analysis. This is the academic framing — cite the data source type (curated DB, API, scrape), evidence categories, and why the source is appropriate for NP.

### 3. Data Source

Name, URL, description of what it aggregates, evidence types as a markdown table. For APIs: authentication requirements, rate limits, free-vs-paid status. This section makes the methodology reproducible.

### 4. Pipeline Steps (one subsection per step)

For each `NN_stepname/` directory:

```markdown
### Step N — `NN_stepname/`

**Input:** path + description (row count if known)

**What it does:**
Numbered list of the logical operations (resolve IDs, paginate, dedupe, normalize, etc.)

**Output:** comma-separated list of output files + manifest

**Key columns in {primary_csv}:**
| Column | Description |
|---|---|
| col | what it means |
```

Include caching behavior if the step uses a cache.

### 5. Output Schema Reference

One subsection per final output table. Header: `### \`tablename.csv\``. Subtext: "Matches the `{tablename}` database table." Then:

```markdown
| Column        | Type    | Description                                  |
| ------------- | ------- | -------------------------------------------- |
| pk_column     | UUID v5 | Primary key — deterministic from {input_key} |
| canonical_key | text    | {source}:{id} format — unique lookup key     |
```

Always explain the UUID v5 derivation logic and the `{source}:{id}` canonical_key convention.

### 6. Configuration (`settings.yml`)

Full table of every key in the module's settings.yml:

```markdown
| Key           | Default | Description      |
| ------------- | ------- | ---------------- |
| `section.key` | `value` | what it controls |
```

### 7. How to Run

Subsections:

- **Prerequisites** — activate venv: `etl\.venv\Scripts\Activate.ps1`
- **Full pipeline** — `python etl/{module}/main.py`
- **Single stage** — `python etl/{module}/main.py --start N --end N`
- **Re-fetch / bypass cache** — `--no-cache` flag or delete cache dir
- **Dry run** — `--dry-run`
- **Unit tests** — `python -m pytest etl/tests/test_{module}_utils.py -v`

### 8. Output Interpretation

- Show the `export_manifest.json` structure with expected value ranges
- Show `validation_report.json` key fields
- Provide a Python spot-check snippet for known biological ground truths (e.g., known drug targets for a disease, known plant families)

### 9. Idempotency

Explain what makes the pipeline safe to re-run: cache hits, deterministic UUIDs, overwrite behavior. Include the command to force a complete re-fetch if needed.

---

## Style Rules

- **Academic framing**: In the Purpose and Data Source sections, use language suitable for Methods sections of a research paper (cite what the source aggregates, how it's curated, why it's authoritative).
- **Operational framing**: In Steps and How to Run, write as a runbook — exact commands, expected output counts, what to do when something fails.
- **Schema tables**: Always note UUID v5 determinism and the `{source}:{id}` canonical_key convention. These are the FK guarantees that make DB import safe.
- **Column descriptions**: Explain the _meaning_, not just the type. "NCBI taxonomy ID — always 9606 (Homo sapiens)" is better than "int".
- **Known biological ground truths**: Always include at least one spot-check example. These let a reader verify the data is biologically sane without querying the DB.

## What NOT to Include

- Implementation details (how the code works internally) — that goes in CLAUDE.md
- Git history or session-specific notes
- Temporary debugging instructions
- Anything that will be stale after the next pipeline run
