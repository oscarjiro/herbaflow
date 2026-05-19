# Herbaflow Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI backend that exposes Herbaflow's plant/compound/disease data and orchestrates an 8-stage network pharmacology analysis pipeline.

**Architecture:** Layered FastAPI app (routers → services → repositories) backed by SQLModel + asyncpg against Supabase. Analysis pipeline runs as asyncio background tasks; each stage writes results to `analysis_runs.stage_results` JSONB. Guided mode pauses after each stage for user approval via `POST /analyses/{id}/approve`.

**Tech Stack:** Python 3.11, FastAPI, SQLModel, asyncpg, httpx, NetworkX, scipy, uv, pytest

---

## File Map

```
backend/
├── pyproject.toml
├── .python-version
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── plant.py          # Plant, PlantAlias
│   │   ├── compound.py       # Compound, CompoundAlias, PlantCompound
│   │   ├── disease.py        # Disease, DiseaseAlias
│   │   ├── target.py         # Target, TargetAlias, CompoundTarget, DiseaseTarget, PpiEdge
│   │   └── analysis.py       # AnalysisRun, AnalysisRunPlant, AnalysisRunCompound, AnalysisRunTarget, TargetRanking, Pathway, TargetPathway
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── plant.py
│   │   ├── compound.py
│   │   ├── disease.py
│   │   └── analysis.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── plants.py
│   │   ├── compounds.py
│   │   ├── diseases.py
│   │   └── analyses.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── compound_service.py
│   │   ├── disease_service.py
│   │   └── analysis_service.py
│   └── repositories/
│       ├── __init__.py
│       ├── compound_repo.py
│       ├── disease_repo.py
│       ├── target_repo.py
│       └── analysis_repo.py
├── analysis/
│   ├── __init__.py
│   ├── models.py             # StageResult, PipelineInput, PipelineConfig, AdmeParams, etc.
│   ├── pipeline.py           # run_stage(), advance_pipeline()
│   └── stages/
│       ├── __init__.py
│       ├── stage1_selection.py
│       ├── stage2_adme.py
│       ├── stage3_targets.py
│       ├── stage4_disease_targets.py
│       ├── stage5_overlap.py
│       ├── stage6_ppi.py
│       ├── stage7_hub_genes.py
│       └── stage8_enrichment.py
├── integrations/
│   ├── __init__.py
│   ├── chembl.py
│   ├── open_targets.py
│   ├── stringdb.py
│   └── gprofiler.py
├── supabase/migrations/
│   ├── 20260518000001_extend_analysis_runs.sql
│   ├── 20260518000002_verify_compound_columns.sql
│   └── 20260518000003_add_pchembl_to_compound_targets.sql
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_adme.py
    │   ├── test_overlap.py
    │   └── test_centrality.py
    └── integration/
        └── test_api.py
```

---

## Task 1: Scaffold project

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.python-version`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/analysis/__init__.py` (empty)
- Create: `backend/integrations/__init__.py` (empty)
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/tests/unit/__init__.py` (empty)
- Create: `backend/tests/integration/__init__.py` (empty)

- [ ] **Step 1: Create backend directory and pyproject.toml**

```toml
# backend/pyproject.toml
[project]
name = "herbaflow-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlmodel>=0.0.22",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "httpx>=0.27.0",
    "networkx>=3.3",
    "scipy>=1.13.0",
    "pydantic-settings>=2.3.0",
    "python-dotenv>=1.0.0",
    "numpy>=1.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.23.0",
    "pytest-httpx>=0.30.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.uv]
dev-dependencies = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.23.0",
    "pytest-httpx>=0.30.0",
]
```

- [ ] **Step 2: Set Python version and install deps**

```
3.11
```
Save as `backend/.python-version`, then from `backend/` directory:
```bash
uv sync
```
Expected: uv creates `.venv/` and installs all packages without error.

- [ ] **Step 3: Create all `__init__.py` placeholder files**

Create empty files at these paths (all relative to `backend/`):
```
app/__init__.py
app/models/__init__.py
app/schemas/__init__.py
app/routers/__init__.py
app/services/__init__.py
app/repositories/__init__.py
analysis/__init__.py
analysis/stages/__init__.py
integrations/__init__.py
tests/__init__.py
tests/unit/__init__.py
tests/integration/__init__.py
```

- [ ] **Step 4: Commit scaffold**

```bash
git add backend/
git commit -m "chore(backend): scaffold FastAPI project with uv"
```

---

## Task 2: Config and database connection

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`

- [ ] **Step 1: Write config.py**

`pydantic-settings` reads from environment variables or `.env` files. The `.env` file lives at the project root (`C:\code\web\herbaflow\.env`), one level above `backend/`.

```python
# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    database_url: str
    disgenet_api_key: str = ""  # Optional; not needed currently

    model_config = {
        "env_file": str(Path(__file__).parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        # Convert sync postgres:// to async postgresql+asyncpg://
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        # Supabase requires SSL
        if "supabase" in url and "ssl" not in url:
            url += "?ssl=require"
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Write database.py**

SQLModel async requires SQLAlchemy's `create_async_engine`. The `AsyncSession` from `sqlmodel.ext.asyncio.session` adds the `.exec()` method that SQLModel uses for typed queries.

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession as SAAsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py backend/app/database.py
git commit -m "feat(backend): add config and async database connection"
```

---

## Task 3: DB migrations

**Files:**
- Create: `backend/supabase/migrations/20260518000001_extend_analysis_runs.sql`
- Create: `backend/supabase/migrations/20260518000002_verify_compound_columns.sql`
- Create: `backend/supabase/migrations/20260518000003_add_pchembl_to_compound_targets.sql`

These migrations extend the existing Supabase schema. Run via Supabase MCP or `supabase db push`.

- [ ] **Step 1: Write migration 1 — extend analysis_runs**

```sql
-- backend/supabase/migrations/20260518000001_extend_analysis_runs.sql
-- Adds guided-mode state columns to analysis_runs.
-- current_stage: 1-8, null = not started
-- stage_results: JSONB map {stage_1: {...}, stage_2: {...}} written by pipeline
-- mode: 'auto' (pipeline runs end-to-end) | 'guided' (pauses for approval per stage)

ALTER TABLE analysis_runs
  ADD COLUMN IF NOT EXISTS current_stage   integer,
  ADD COLUMN IF NOT EXISTS stage_results   jsonb        NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS mode            text         NOT NULL DEFAULT 'auto',
  ADD COLUMN IF NOT EXISTS completed_at    timestamptz,
  ADD COLUMN IF NOT EXISTS error_message   text,
  ADD COLUMN IF NOT EXISTS updated_at      timestamptz  NOT NULL DEFAULT now();

-- Backfill updated_at for existing rows
UPDATE analysis_runs SET updated_at = created_at WHERE updated_at IS NULL;
```

- [ ] **Step 2: Write migration 2 — verify compound columns**

```sql
-- backend/supabase/migrations/20260518000002_verify_compound_columns.sql
-- Adds ADME columns that the lipinski ETL patch computed but may not be in DB schema.
-- IF NOT EXISTS is safe to run repeatedly.

ALTER TABLE compounds
  ADD COLUMN IF NOT EXISTS rotatable_bonds    integer,
  ADD COLUMN IF NOT EXISTS num_ro5_violations integer,
  ADD COLUMN IF NOT EXISTS qed_score          float,
  ADD COLUMN IF NOT EXISTS np_likeness_score  float,
  ADD COLUMN IF NOT EXISTS lipinski_source    text;
```

- [ ] **Step 3: Write migration 3 — add pchembl_value to compound_targets**

```sql
-- backend/supabase/migrations/20260518000003_add_pchembl_to_compound_targets.sql
-- pChEMBL = -log10(IC50 in molar). Value >= 5 means IC50 <= 10uM (active).
-- Null for STITCH-sourced targets that don't have pChEMBL data.

ALTER TABLE compound_targets
  ADD COLUMN IF NOT EXISTS pchembl_value float;
```

- [ ] **Step 4: Apply migrations via Supabase MCP**

Use the `mcp__plugin_supabase_supabase__apply_migration` tool to run each migration, or from the project root:
```bash
supabase db push
```

- [ ] **Step 5: Verify migrations applied**

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'analysis_runs'
  AND column_name IN ('current_stage', 'stage_results', 'mode', 'completed_at', 'error_message');
```
Expected: 5 rows returned.

- [ ] **Step 6: Commit migrations**

```bash
git add backend/supabase/
git commit -m "feat(schema): extend analysis_runs and verify compound ADME columns"
```

---

## Task 4: SQLModel models — plants and compounds

**Files:**
- Create: `backend/app/models/plant.py`
- Create: `backend/app/models/compound.py`

SQLModel `table=True` models mirror the DB schema exactly. Column names match what's in Supabase. Use `Optional` for nullable columns.

- [ ] **Step 1: Write plant.py**

```python
# backend/app/models/plant.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field, SQLModel


class Plant(SQLModel, table=True):
    __tablename__ = "plants"

    plant_id: UUID = Field(primary_key=True)
    canonical_key: str = Field(unique=True)
    canonical_scientific_name: str
    authorship: Optional[str] = None
    family_name: Optional[str] = None
    taxonomic_status: Optional[str] = None
    rank: Optional[str] = None
    gbif_usage_key: Optional[int] = None
    gbif_accepted_usage_key: Optional[int] = None
    gbif_species_key: Optional[int] = None
    gbif_genus_key: Optional[int] = None
    gbif_family_key: Optional[int] = None
    gbif_kingdom_key: Optional[int] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id")
    retrieved_at: Optional[datetime] = None
    confidence: Optional[float] = None


class PlantAlias(SQLModel, table=True):
    __tablename__ = "plant_aliases"

    alias_id: UUID = Field(primary_key=True)
    plant_id: UUID = Field(foreign_key="plants.plant_id")
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id")
    retrieved_at: Optional[datetime] = None
```

- [ ] **Step 2: Write compound.py**

```python
# backend/app/models/compound.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field, SQLModel


class Compound(SQLModel, table=True):
    __tablename__ = "compounds"

    compound_id: UUID = Field(primary_key=True)
    canonical_key: str = Field(unique=True)
    canonical_name: str
    inchi_key: Optional[str] = None
    smiles: Optional[str] = None
    cas_id: Optional[str] = None
    pubchem_cid: Optional[str] = None
    chembl_id: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    tpsa: Optional[float] = None
    logp: Optional[float] = None
    hbond_donors: Optional[int] = None
    hbond_acceptors: Optional[int] = None
    rotatable_bonds: Optional[int] = None
    num_ro5_violations: Optional[int] = None
    qed_score: Optional[float] = None
    np_likeness_score: Optional[float] = None
    lipinski_source: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id")
    retrieved_at: Optional[datetime] = None
    confidence: Optional[float] = None


class CompoundAlias(SQLModel, table=True):
    __tablename__ = "compound_aliases"

    compound_alias_id: UUID = Field(primary_key=True)
    compound_id: UUID = Field(foreign_key="compounds.compound_id")
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id")
    retrieved_at: Optional[datetime] = None


class PlantCompound(SQLModel, table=True):
    __tablename__ = "plant_compounds"

    plant_compound_id: UUID = Field(primary_key=True)
    plant_id: UUID = Field(foreign_key="plants.plant_id")
    compound_id: UUID = Field(foreign_key="compounds.compound_id")
    source_plant_raw_id: Optional[str] = None
    source_compound_raw_id: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    evidence_type: Optional[str] = None
    confidence: Optional[float] = None
    retrieved_at: Optional[datetime] = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/plant.py backend/app/models/compound.py
git commit -m "feat(backend): add Plant and Compound SQLModel models"
```

---

## Task 5: SQLModel models — diseases, targets, analysis

**Files:**
- Create: `backend/app/models/disease.py`
- Create: `backend/app/models/target.py`
- Create: `backend/app/models/analysis.py`

- [ ] **Step 1: Write disease.py**

```python
# backend/app/models/disease.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field, SQLModel


class Disease(SQLModel, table=True):
    __tablename__ = "diseases"

    disease_id: UUID = Field(primary_key=True)
    canonical_key: str = Field(unique=True)
    disease_name: str
    ontology_id: Optional[str] = None
    ontology_source: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id")
    retrieved_at: Optional[datetime] = None
    confidence: Optional[float] = None


class DiseaseAlias(SQLModel, table=True):
    __tablename__ = "disease_aliases"

    disease_alias_id: UUID = Field(primary_key=True)
    disease_id: UUID = Field(foreign_key="diseases.disease_id")
    alias_name: str
    alias_key: Optional[str] = None
    alias_type: Optional[str] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    retrieved_at: Optional[datetime] = None
```

- [ ] **Step 2: Write target.py**

```python
# backend/app/models/target.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field, SQLModel


class Target(SQLModel, table=True):
    __tablename__ = "targets"

    target_id: UUID = Field(primary_key=True)
    canonical_key: str = Field(unique=True)
    gene_symbol: Optional[str] = None
    protein_name: Optional[str] = None
    uniprot_accession: Optional[str] = None
    organism_tax_id: Optional[int] = None
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    source_url: Optional[str] = None
    source_batch_id: Optional[UUID] = Field(default=None, foreign_key="import_batches.batch_id")
    retrieved_at: Optional[datetime] = None
    confidence: Optional[float] = None


class CompoundTarget(SQLModel, table=True):
    __tablename__ = "compound_targets"

    compound_target_id: UUID = Field(primary_key=True)
    compound_id: UUID = Field(foreign_key="compounds.compound_id")
    target_id: UUID = Field(foreign_key="targets.target_id")
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    prediction_method: Optional[str] = None
    evidence_type: Optional[str] = None
    score: Optional[float] = None
    confidence: Optional[float] = None
    pchembl_value: Optional[float] = None
    retrieved_at: Optional[datetime] = None


class DiseaseTarget(SQLModel, table=True):
    __tablename__ = "disease_targets"

    disease_target_id: UUID = Field(primary_key=True)
    disease_id: UUID = Field(foreign_key="diseases.disease_id")
    target_id: UUID = Field(foreign_key="targets.target_id")
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    association_type: Optional[str] = None
    score: Optional[float] = None
    confidence: Optional[float] = None
    retrieved_at: Optional[datetime] = None


class PpiEdge(SQLModel, table=True):
    __tablename__ = "ppi_edges"

    ppi_edge_id: UUID = Field(primary_key=True)
    target_a_id: UUID = Field(foreign_key="targets.target_id")
    target_b_id: UUID = Field(foreign_key="targets.target_id")
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    combined_score: Optional[float] = None
    experimental_score: Optional[float] = None
    database_score: Optional[float] = None
    textmining_score: Optional[float] = None
    coexpression_score: Optional[float] = None
    neighborhood_score: Optional[float] = None
    fusion_score: Optional[float] = None
    cooccurrence_score: Optional[float] = None
    retrieved_at: Optional[datetime] = None
```

- [ ] **Step 3: Write analysis.py**

```python
# backend/app/models/analysis.py
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_runs"

    analysis_id: UUID = Field(primary_key=True)
    analysis_name: str
    notes: Optional[str] = None
    parameters: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    stage_results: Optional[dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "pending"
    mode: str = "auto"
    current_stage: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


class TargetRanking(SQLModel, table=True):
    __tablename__ = "target_rankings"

    ranking_id: UUID = Field(primary_key=True)
    analysis_id: UUID = Field(foreign_key="analysis_runs.analysis_id")
    target_id: UUID = Field(foreign_key="targets.target_id")
    degree_centrality: Optional[float] = None
    betweenness_centrality: Optional[float] = None
    closeness_centrality: Optional[float] = None
    eigenvector_centrality: Optional[float] = None
    disease_association_score: Optional[float] = None
    compound_support_score: Optional[float] = None
    final_score: Optional[float] = None
    rank_position: Optional[int] = None
    created_at: Optional[datetime] = None


class Pathway(SQLModel, table=True):
    __tablename__ = "pathways"

    pathway_id: UUID = Field(primary_key=True)
    pathway_code: Optional[str] = None
    pathway_name: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None


class TargetPathway(SQLModel, table=True):
    __tablename__ = "target_pathways"

    target_pathway_id: UUID = Field(primary_key=True)
    target_id: UUID = Field(foreign_key="targets.target_id")
    pathway_id: UUID = Field(foreign_key="pathways.pathway_id")
    source_id: Optional[UUID] = Field(default=None, foreign_key="source_systems.source_id")
    p_value: Optional[float] = None
    fdr: Optional[float] = None
    confidence: Optional[float] = None
```

- [ ] **Step 4: Update models/__init__.py to export all models**

```python
# backend/app/models/__init__.py
from .plant import Plant, PlantAlias
from .compound import Compound, CompoundAlias, PlantCompound
from .disease import Disease, DiseaseAlias
from .target import Target, CompoundTarget, DiseaseTarget, PpiEdge
from .analysis import AnalysisRun, TargetRanking, Pathway, TargetPathway

__all__ = [
    "Plant", "PlantAlias",
    "Compound", "CompoundAlias", "PlantCompound",
    "Disease", "DiseaseAlias",
    "Target", "CompoundTarget", "DiseaseTarget", "PpiEdge",
    "AnalysisRun", "TargetRanking", "Pathway", "TargetPathway",
]
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat(backend): add SQLModel models for all domain entities"
```

---

## Task 6: FastAPI app and health endpoint

**Files:**
- Create: `backend/app/main.py`

- [ ] **Step 1: Write main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Herbaflow API",
    description="Network pharmacology platform for Indonesian medicinal plants",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 2: Test the server starts and /health responds**

From `backend/` directory:
```bash
uv run uvicorn app.main:app --reload --port 8000
```
Expected: `Uvicorn running on http://127.0.0.1:8000`

In another terminal:
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 3: Also verify OpenAPI docs are auto-generated**

Open `http://localhost:8000/docs` in browser. Expected: Swagger UI loads with one endpoint.

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): add FastAPI app with /health endpoint"
```

---

## Task 7: Reference repositories (plants, compounds, diseases)

Repositories handle all DB queries. They receive an `AsyncSession` and return typed SQLModel objects. No business logic here.

**Files:**
- Create: `backend/app/repositories/compound_repo.py`
- Create: `backend/app/repositories/disease_repo.py`
- Create: `backend/app/repositories/target_repo.py`

- [ ] **Step 1: Write compound_repo.py**

```python
# backend/app/repositories/compound_repo.py
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.compound import Compound, PlantCompound
from app.models.plant import Plant


async def get_all_compounds(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    has_smiles: bool | None = None,
    has_chembl: bool | None = None,
) -> list[Compound]:
    q = select(Compound)
    if has_smiles is True:
        q = q.where(Compound.smiles.isnot(None))
    if has_chembl is True:
        q = q.where(Compound.chembl_id.isnot(None))
    q = q.offset(offset).limit(limit)
    result = await session.exec(q)
    return result.all()


async def get_compound_by_id(session: AsyncSession, compound_id: UUID) -> Compound | None:
    result = await session.exec(select(Compound).where(Compound.compound_id == compound_id))
    return result.first()


async def get_compounds_for_plant(
    session: AsyncSession, plant_id: UUID
) -> list[Compound]:
    q = (
        select(Compound)
        .join(PlantCompound, PlantCompound.compound_id == Compound.compound_id)
        .where(PlantCompound.plant_id == plant_id)
    )
    result = await session.exec(q)
    return result.all()


async def get_compounds_for_plants(
    session: AsyncSession, plant_ids: list[UUID]
) -> list[Compound]:
    """Used by analysis Stage 1 to load all compounds for selected plants."""
    q = (
        select(Compound)
        .join(PlantCompound, PlantCompound.compound_id == Compound.compound_id)
        .where(PlantCompound.plant_id.in_(plant_ids))
        .distinct()
    )
    result = await session.exec(q)
    return result.all()


async def count_compounds_for_plant(session: AsyncSession, plant_id: UUID) -> int:
    from sqlalchemy import func
    from sqlmodel import select as sm_select
    result = await session.exec(
        sm_select(func.count(PlantCompound.compound_id)).where(
            PlantCompound.plant_id == plant_id
        )
    )
    return result.one()
```

- [ ] **Step 2: Write disease_repo.py**

```python
# backend/app/repositories/disease_repo.py
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.disease import Disease
from app.models.target import DiseaseTarget, Target


async def get_all_diseases(session: AsyncSession) -> list[Disease]:
    result = await session.exec(select(Disease).order_by(Disease.disease_name))
    return result.all()


async def get_disease_by_id(session: AsyncSession, disease_id: UUID) -> Disease | None:
    result = await session.exec(
        select(Disease).where(Disease.disease_id == disease_id)
    )
    return result.first()


async def get_targets_for_disease(
    session: AsyncSession, disease_id: UUID, min_score: float = 0.0
) -> list[tuple[Target, float]]:
    """Returns (target, association_score) pairs for a disease."""
    q = (
        select(Target, DiseaseTarget.score)
        .join(DiseaseTarget, DiseaseTarget.target_id == Target.target_id)
        .where(DiseaseTarget.disease_id == disease_id)
        .where(DiseaseTarget.score >= min_score)
        .order_by(DiseaseTarget.score.desc())
    )
    result = await session.exec(q)
    return result.all()
```

- [ ] **Step 3: Write target_repo.py**

```python
# backend/app/repositories/target_repo.py
from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.target import Target, CompoundTarget


async def get_target_by_gene_symbol(
    session: AsyncSession, gene_symbol: str
) -> Target | None:
    result = await session.exec(
        select(Target).where(Target.gene_symbol == gene_symbol.upper())
    )
    return result.first()


async def get_targets_for_compound(
    session: AsyncSession, compound_id: UUID, min_pchembl: float | None = None
) -> list[tuple[Target, float | None]]:
    q = (
        select(Target, CompoundTarget.pchembl_value)
        .join(CompoundTarget, CompoundTarget.target_id == Target.target_id)
        .where(CompoundTarget.compound_id == compound_id)
    )
    if min_pchembl is not None:
        q = q.where(
            (CompoundTarget.pchembl_value >= min_pchembl)
            | CompoundTarget.pchembl_value.is_(None)
        )
    result = await session.exec(q)
    return result.all()


async def upsert_target(session: AsyncSession, target: Target) -> Target:
    """Insert or skip if canonical_key already exists."""
    existing = await session.exec(
        select(Target).where(Target.canonical_key == target.canonical_key)
    )
    found = existing.first()
    if found:
        return found
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/repositories/
git commit -m "feat(backend): add compound, disease, target repositories"
```

---

## Task 8: Schemas and reference routers

**Files:**
- Create: `backend/app/schemas/compound.py`
- Create: `backend/app/schemas/plant.py`
- Create: `backend/app/schemas/disease.py`
- Create: `backend/app/routers/plants.py`
- Create: `backend/app/routers/compounds.py`
- Create: `backend/app/routers/diseases.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write schemas**

```python
# backend/app/schemas/plant.py
from pydantic import BaseModel
from uuid import UUID


class PlantResponse(BaseModel):
    plant_id: UUID
    canonical_scientific_name: str
    family_name: str | None
    compound_count: int = 0
```

```python
# backend/app/schemas/compound.py
from pydantic import BaseModel
from uuid import UUID


class CompoundResponse(BaseModel):
    compound_id: UUID
    canonical_name: str
    smiles: str | None
    chembl_id: str | None
    pubchem_cid: str | None
    molecular_weight: float | None
    logp: float | None
    tpsa: float | None
    hbond_donors: int | None
    hbond_acceptors: int | None
    rotatable_bonds: int | None
    np_likeness_score: float | None
    num_ro5_violations: int | None
    lipinski_source: str | None
```

```python
# backend/app/schemas/disease.py
from pydantic import BaseModel
from uuid import UUID


class DiseaseResponse(BaseModel):
    disease_id: UUID
    disease_name: str
    ontology_id: str | None
    ontology_source: str | None
```

- [ ] **Step 2: Write plants router**

```python
# backend/app/routers/plants.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.schemas.plant import PlantResponse
from app.schemas.compound import CompoundResponse
from app.repositories import compound_repo
from sqlmodel import select
from app.models.plant import Plant

router = APIRouter(prefix="/plants", tags=["plants"])


@router.get("", response_model=list[PlantResponse])
async def list_plants(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Plant).order_by(Plant.canonical_scientific_name))
    plants = result.all()
    out = []
    for plant in plants:
        count = await compound_repo.count_compounds_for_plant(session, plant.plant_id)
        out.append(PlantResponse(
            plant_id=plant.plant_id,
            canonical_scientific_name=plant.canonical_scientific_name,
            family_name=plant.family_name,
            compound_count=count,
        ))
    return out


@router.get("/{plant_id}", response_model=PlantResponse)
async def get_plant(plant_id: UUID, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Plant).where(Plant.plant_id == plant_id))
    plant = result.first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    count = await compound_repo.count_compounds_for_plant(session, plant_id)
    return PlantResponse(
        plant_id=plant.plant_id,
        canonical_scientific_name=plant.canonical_scientific_name,
        family_name=plant.family_name,
        compound_count=count,
    )


@router.get("/{plant_id}/compounds", response_model=list[CompoundResponse])
async def get_plant_compounds(plant_id: UUID, session: AsyncSession = Depends(get_session)):
    compounds = await compound_repo.get_compounds_for_plant(session, plant_id)
    return [CompoundResponse(**c.model_dump()) for c in compounds]
```

- [ ] **Step 3: Write compounds and diseases routers**

```python
# backend/app/routers/compounds.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.schemas.compound import CompoundResponse
from app.repositories import compound_repo

router = APIRouter(prefix="/compounds", tags=["compounds"])


@router.get("", response_model=list[CompoundResponse])
async def list_compounds(
    limit: int = Query(100, le=500),
    offset: int = 0,
    has_smiles: bool | None = None,
    has_chembl: bool | None = None,
    session: AsyncSession = Depends(get_session),
):
    compounds = await compound_repo.get_all_compounds(
        session, limit=limit, offset=offset, has_smiles=has_smiles, has_chembl=has_chembl
    )
    return [CompoundResponse(**c.model_dump()) for c in compounds]


@router.get("/{compound_id}", response_model=CompoundResponse)
async def get_compound(compound_id: UUID, session: AsyncSession = Depends(get_session)):
    compound = await compound_repo.get_compound_by_id(session, compound_id)
    if not compound:
        raise HTTPException(status_code=404, detail="Compound not found")
    return CompoundResponse(**compound.model_dump())
```

```python
# backend/app/routers/diseases.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.schemas.disease import DiseaseResponse
from app.repositories import disease_repo

router = APIRouter(prefix="/diseases", tags=["diseases"])


@router.get("", response_model=list[DiseaseResponse])
async def list_diseases(session: AsyncSession = Depends(get_session)):
    diseases = await disease_repo.get_all_diseases(session)
    return [DiseaseResponse(**d.model_dump()) for d in diseases]


@router.get("/{disease_id}", response_model=DiseaseResponse)
async def get_disease(disease_id: UUID, session: AsyncSession = Depends(get_session)):
    disease = await disease_repo.get_disease_by_id(session, disease_id)
    if not disease:
        raise HTTPException(status_code=404, detail="Disease not found")
    return DiseaseResponse(**disease.model_dump())
```

- [ ] **Step 4: Register routers in main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import plants, compounds, diseases

app = FastAPI(
    title="Herbaflow API",
    description="Network pharmacology platform for Indonesian medicinal plants",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plants.router)
app.include_router(compounds.router)
app.include_router(diseases.router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 5: Smoke-test reference endpoints**

Start server, then:
```bash
curl http://localhost:8000/plants | python -m json.tool | head -20
curl http://localhost:8000/diseases
curl "http://localhost:8000/compounds?limit=5&has_chembl=true" | python -m json.tool
```
Expected: JSON arrays with real data from Supabase.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/ backend/app/routers/ backend/app/main.py
git commit -m "feat(backend): add plants, compounds, diseases endpoints"
```

---

## Task 9: Analysis pipeline models

**Files:**
- Create: `backend/analysis/models.py`

These are plain dataclasses/Pydantic models used internally by the pipeline — not DB models.

- [ ] **Step 1: Write analysis/models.py**

```python
# backend/analysis/models.py
from dataclasses import dataclass, field
from uuid import UUID
from typing import Any


@dataclass
class AdmeParams:
    max_mw: float = 500.0
    max_logp: float = 5.0
    max_hbd: int = 5
    max_hba: int = 10
    max_tpsa: float = 140.0
    max_rotatable_bonds: int = 10
    apply_veber: bool = True
    apply_pains: bool = False
    np_exception_threshold: float = 0.5


@dataclass
class TargetParams:
    min_pchembl: float = 5.0
    human_only: bool = True


@dataclass
class DiseaseTargetParams:
    min_score: float = 0.3


@dataclass
class PpiParams:
    min_confidence: float = 0.4


@dataclass
class HubGeneParams:
    top_n: int = 20


@dataclass
class EnrichmentParams:
    fdr_threshold: float = 0.05
    sources: list[str] = field(default_factory=lambda: ["GO:BP", "GO:MF", "GO:CC", "KEGG"])


@dataclass
class PipelineConfig:
    adme: AdmeParams = field(default_factory=AdmeParams)
    target: TargetParams = field(default_factory=TargetParams)
    disease_targets: DiseaseTargetParams = field(default_factory=DiseaseTargetParams)
    ppi: PpiParams = field(default_factory=PpiParams)
    hub_genes: HubGeneParams = field(default_factory=HubGeneParams)
    enrichment: EnrichmentParams = field(default_factory=EnrichmentParams)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "PipelineConfig":
        if not d:
            return cls()
        return cls(
            adme=AdmeParams(**d.get("adme", {})),
            target=TargetParams(**d.get("target", {})),
            disease_targets=DiseaseTargetParams(**d.get("disease_targets", {})),
            ppi=PpiParams(**d.get("ppi", {})),
            hub_genes=HubGeneParams(**d.get("hub_genes", {})),
            enrichment=EnrichmentParams(**d.get("enrichment", {})),
        )


@dataclass
class CompoundRecord:
    """Minimal compound data needed by pipeline stages."""
    compound_id: UUID
    canonical_name: str
    smiles: str | None
    chembl_id: str | None
    pubchem_cid: str | None
    molecular_weight: float | None
    logp: float | None
    hbond_donors: int | None
    hbond_acceptors: int | None
    tpsa: float | None
    rotatable_bonds: int | None
    np_likeness_score: float | None
    num_ro5_violations: int | None


@dataclass
class TargetRecord:
    gene_symbol: str
    uniprot_accession: str | None
    source: str  # 'chembl' | 'stitch' | 'disease'
    pchembl_value: float | None = None
    association_score: float | None = None
    compound_ids: list[UUID] = field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
git add backend/analysis/models.py
git commit -m "feat(backend): add pipeline configuration and internal data models"
```

---

## Task 10: Analysis repo, schemas, and create endpoint

**Files:**
- Create: `backend/app/repositories/analysis_repo.py`
- Create: `backend/app/schemas/analysis.py`
- Create: `backend/app/routers/analyses.py` (create + status only for now)
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write analysis_repo.py**

```python
# backend/app/repositories/analysis_repo.py
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.analysis import AnalysisRun


async def create_run(
    session: AsyncSession,
    name: str,
    mode: str,
    parameters: dict,
) -> AnalysisRun:
    run = AnalysisRun(
        analysis_id=uuid4(),
        analysis_name=name,
        mode=mode,
        parameters=parameters,
        status="pending",
        stage_results={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, analysis_id: UUID) -> AnalysisRun | None:
    result = await session.exec(
        select(AnalysisRun).where(AnalysisRun.analysis_id == analysis_id)
    )
    return result.first()


async def list_runs(session: AsyncSession) -> list[AnalysisRun]:
    result = await session.exec(
        select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    )
    return result.all()


async def update_run_status(
    session: AsyncSession,
    analysis_id: UUID,
    status: str,
    current_stage: int | None = None,
    stage_results: dict | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> AnalysisRun:
    run = await get_run(session, analysis_id)
    run.status = status
    run.updated_at = datetime.now(timezone.utc)
    if current_stage is not None:
        run.current_stage = current_stage
    if stage_results is not None:
        # Merge new results into existing; don't overwrite all stages
        existing = run.stage_results or {}
        existing.update(stage_results)
        run.stage_results = existing
    if error_message is not None:
        run.error_message = error_message
    if completed:
        run.completed_at = datetime.now(timezone.utc)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run
```

- [ ] **Step 2: Write analysis schemas**

```python
# backend/app/schemas/analysis.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any


class CreateAnalysisRequest(BaseModel):
    name: str
    mode: str = "guided"  # 'auto' | 'guided'
    plant_ids: list[UUID] = []
    disease_ids: list[UUID] = []
    parameters: dict[str, Any] = {}


class AnalysisStatusResponse(BaseModel):
    analysis_id: UUID
    status: str
    mode: str
    current_stage: int | None
    progress: dict[str, int]  # {done: N, total: 8}
    created_at: datetime | None
    updated_at: datetime | None
    error_message: str | None = None


class AnalysisRunResponse(BaseModel):
    analysis_id: UUID
    analysis_name: str
    status: str
    mode: str
    current_stage: int | None
    stage_results: dict[str, Any]
    parameters: dict[str, Any] | None
    created_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
```

- [ ] **Step 3: Write analyses router (create + list + status)**

```python
# backend/app/routers/analyses.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session, async_session_factory
from app.schemas.analysis import CreateAnalysisRequest, AnalysisStatusResponse, AnalysisRunResponse
from app.repositories import analysis_repo
from analysis.pipeline import start_pipeline

router = APIRouter(prefix="/analyses", tags=["analyses"])

TOTAL_STAGES = 8


def _status_to_done(status: str) -> int:
    """Parse stage number from status string like 'stage_3_running'."""
    if status == "complete":
        return TOTAL_STAGES
    if status.startswith("stage_"):
        try:
            return int(status.split("_")[1]) - 1
        except (IndexError, ValueError):
            return 0
    return 0


@router.post("", response_model=AnalysisStatusResponse, status_code=201)
async def create_analysis(
    body: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    parameters = {
        **body.parameters,
        "_plant_ids": [str(pid) for pid in body.plant_ids],
        "_disease_ids": [str(did) for did in body.disease_ids],
    }
    run = await analysis_repo.create_run(session, body.name, body.mode, parameters)
    # Start pipeline in background — does not block the HTTP response
    background_tasks.add_task(
        start_pipeline, run.analysis_id, body.plant_ids, body.disease_ids, async_session_factory
    )
    return AnalysisStatusResponse(
        analysis_id=run.analysis_id,
        status=run.status,
        mode=run.mode,
        current_stage=run.current_stage,
        progress={"done": 0, "total": TOTAL_STAGES},
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("", response_model=list[AnalysisRunResponse])
async def list_analyses(session: AsyncSession = Depends(get_session)):
    runs = await analysis_repo.list_runs(session)
    return [AnalysisRunResponse(**r.model_dump()) for r in runs]


@router.get("/{analysis_id}/status", response_model=AnalysisStatusResponse)
async def get_status(analysis_id: UUID, session: AsyncSession = Depends(get_session)):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisStatusResponse(
        analysis_id=run.analysis_id,
        status=run.status,
        mode=run.mode,
        current_stage=run.current_stage,
        progress={"done": _status_to_done(run.status), "total": TOTAL_STAGES},
        created_at=run.created_at,
        updated_at=run.updated_at,
        error_message=run.error_message,
    )


@router.get("/{analysis_id}", response_model=AnalysisRunResponse)
async def get_analysis(analysis_id: UUID, session: AsyncSession = Depends(get_session)):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisRunResponse(**run.model_dump())
```

- [ ] **Step 4: Register analyses router in main.py**

Add to `backend/app/main.py`:
```python
from app.routers import plants, compounds, diseases, analyses

# ... existing code ...
app.include_router(analyses.router)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/analysis_repo.py backend/app/schemas/analysis.py backend/app/routers/analyses.py backend/app/main.py
git commit -m "feat(backend): add analysis CRUD endpoints and status polling"
```

---

## Task 11: Pipeline orchestrator skeleton

**Files:**
- Create: `backend/analysis/pipeline.py`

The orchestrator runs one stage at a time. In guided mode it stops after each stage and waits for `POST /analyses/{id}/approve` to start the next.

- [ ] **Step 1: Write analysis/pipeline.py**

```python
# backend/analysis/pipeline.py
import asyncio
import traceback
from uuid import UUID
from sqlalchemy.orm import sessionmaker

from app.repositories import analysis_repo
from analysis.models import PipelineConfig
from analysis.stages import (
    stage1_selection,
    stage2_adme,
    stage3_targets,
    stage4_disease_targets,
    stage5_overlap,
    stage6_ppi,
    stage7_hub_genes,
    stage8_enrichment,
)

STAGE_RUNNERS = {
    1: stage1_selection.run,
    2: stage2_adme.run,
    3: stage3_targets.run,
    4: stage4_disease_targets.run,
    5: stage5_overlap.run,
    6: stage6_ppi.run,
    7: stage7_hub_genes.run,
    8: stage8_enrichment.run,
}


async def run_stage(
    analysis_id: UUID,
    stage_num: int,
    session_factory: sessionmaker,
) -> None:
    """Execute a single stage, write results, advance or pause per mode."""
    async with session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
        if run is None or run.status == "failed":
            return

        config = PipelineConfig.from_dict(run.parameters)
        stage_fn = STAGE_RUNNERS.get(stage_num)

        # Mark stage as running
        await analysis_repo.update_run_status(
            session, analysis_id,
            status=f"stage_{stage_num}_running",
            current_stage=stage_num,
        )

    try:
        async with session_factory() as session:
            run = await analysis_repo.get_run(session, analysis_id)
            stage_result = await stage_fn(run, config, session)

        async with session_factory() as session:
            run = await analysis_repo.get_run(session, analysis_id)
            is_last = stage_num == 8
            if is_last:
                await analysis_repo.update_run_status(
                    session, analysis_id,
                    status="complete",
                    stage_results={f"stage_{stage_num}": stage_result},
                    completed=True,
                )
            elif run.mode == "guided":
                await analysis_repo.update_run_status(
                    session, analysis_id,
                    status=f"stage_{stage_num}_awaiting_approval",
                    stage_results={f"stage_{stage_num}": stage_result},
                )
            else:
                # Auto mode: immediately queue next stage
                await analysis_repo.update_run_status(
                    session, analysis_id,
                    status=f"stage_{stage_num}_complete",
                    stage_results={f"stage_{stage_num}": stage_result},
                )
                asyncio.create_task(
                    run_stage(analysis_id, stage_num + 1, session_factory)
                )

    except Exception as exc:
        async with session_factory() as session:
            await analysis_repo.update_run_status(
                session, analysis_id,
                status="failed",
                error_message=f"Stage {stage_num} failed: {traceback.format_exc()}",
            )


async def start_pipeline(
    analysis_id: UUID,
    plant_ids: list[UUID],
    disease_ids: list[UUID],
    session_factory: sessionmaker,
) -> None:
    """Entry point: store input IDs on the run, then kick off stage 1."""
    async with session_factory() as session:
        run = await analysis_repo.get_run(session, analysis_id)
        # Store plant/disease IDs in parameters for stages to read
        params = run.parameters or {}
        params["_plant_ids"] = [str(p) for p in plant_ids]
        params["_disease_ids"] = [str(d) for d in disease_ids]
        run.parameters = params
        session.add(run)
        await session.commit()

    await run_stage(analysis_id, 1, session_factory)
```

- [ ] **Step 2: Create stage stub files**

Each stage file must export a `run(run, config, session)` async function. Create stubs for all 8:

```python
# backend/analysis/stages/stage1_selection.py
from analysis.models import PipelineConfig, CompoundRecord
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    return {"status": "stub", "stage": 1}
```

Repeat for `stage2_adme.py` through `stage8_enrichment.py`, changing the stage number. These stubs will be replaced task-by-task.

- [ ] **Step 3: Verify pipeline starts**

Start server. POST a new analysis:
```bash
curl -X POST http://localhost:8000/analyses \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "mode": "auto", "plant_ids": [], "disease_ids": []}'
```
Expected: `{"analysis_id": "...", "status": "pending", ...}`

Poll status:
```bash
curl http://localhost:8000/analyses/<id>/status
```
Expected: status advances to `stage_1_complete` (or `stage_8_complete` since all stubs return instantly).

- [ ] **Step 4: Commit**

```bash
git add backend/analysis/
git commit -m "feat(backend): add pipeline orchestrator and stage stubs"
```

---

## Task 12: Stage 2 — ADME filter (TDD)

Stage 2 is pure Python — all Lipinski data is already in the compounds table. No external API calls.

**Files:**
- Create: `backend/tests/unit/test_adme.py`
- Modify: `backend/analysis/stages/stage2_adme.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_adme.py
import pytest
from uuid import uuid4
from analysis.models import AdmeParams, CompoundRecord
from analysis.stages.stage2_adme import filter_compounds


def make_compound(**kwargs) -> CompoundRecord:
    defaults = dict(
        compound_id=uuid4(),
        canonical_name="test",
        smiles=None,
        chembl_id=None,
        pubchem_cid=None,
        molecular_weight=300.0,
        logp=2.0,
        hbond_donors=2,
        hbond_acceptors=4,
        tpsa=60.0,
        rotatable_bonds=5,
        np_likeness_score=0.3,
        num_ro5_violations=0,
    )
    defaults.update(kwargs)
    return CompoundRecord(**defaults)


def test_passes_all_filters():
    compound = make_compound()
    params = AdmeParams()
    result = filter_compounds([compound], params)
    assert result["passed"][0].compound_id == compound.compound_id
    assert result["failed"] == []
    assert result["np_exceptions"] == []


def test_fails_mw():
    compound = make_compound(molecular_weight=600.0)
    result = filter_compounds([compound], AdmeParams())
    assert result["failed"][0].compound_id == compound.compound_id


def test_fails_logp():
    compound = make_compound(logp=6.0)
    result = filter_compounds([compound], AdmeParams())
    assert len(result["failed"]) == 1


def test_np_exception_flagged_not_excluded():
    # Compound fails MW but has high np_likeness_score — should go to np_exceptions
    compound = make_compound(molecular_weight=700.0, np_likeness_score=0.8)
    result = filter_compounds([compound], AdmeParams(np_exception_threshold=0.5))
    assert result["passed"] == []
    assert result["np_exceptions"][0].compound_id == compound.compound_id
    assert result["failed"] == []


def test_veber_filter():
    compound = make_compound(tpsa=200.0, rotatable_bonds=15)
    result = filter_compounds([compound], AdmeParams(apply_veber=True))
    assert len(result["failed"]) == 1


def test_veber_not_applied_when_disabled():
    compound = make_compound(tpsa=200.0, rotatable_bonds=15)
    result = filter_compounds([compound], AdmeParams(apply_veber=False))
    assert len(result["passed"]) == 1


def test_missing_mw_skips_mw_filter():
    compound = make_compound(molecular_weight=None)
    result = filter_compounds([compound], AdmeParams())
    # Can't evaluate MW filter — compound passes (include-with-null-data)
    assert len(result["passed"]) == 1
```

- [ ] **Step 2: Run tests, confirm they fail**

From `backend/`:
```bash
uv run pytest tests/unit/test_adme.py -v
```
Expected: `ImportError` or `AttributeError` — `filter_compounds` not yet defined.

- [ ] **Step 3: Implement stage2_adme.py**

```python
# backend/analysis/stages/stage2_adme.py
from analysis.models import AdmeParams, CompoundRecord, PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import compound_repo
from uuid import UUID


def filter_compounds(
    compounds: list[CompoundRecord], params: AdmeParams
) -> dict:
    passed, failed, np_exceptions = [], [], []

    for c in compounds:
        violations = []

        # Lipinski Ro5
        if c.molecular_weight is not None and c.molecular_weight > params.max_mw:
            violations.append("mw")
        if c.logp is not None and c.logp > params.max_logp:
            violations.append("logp")
        if c.hbond_donors is not None and c.hbond_donors > params.max_hbd:
            violations.append("hbd")
        if c.hbond_acceptors is not None and c.hbond_acceptors > params.max_hba:
            violations.append("hba")

        # Veber rules
        if params.apply_veber:
            if c.tpsa is not None and c.tpsa > params.max_tpsa:
                violations.append("tpsa")
            if c.rotatable_bonds is not None and c.rotatable_bonds > params.max_rotatable_bonds:
                violations.append("rotatable_bonds")

        if not violations:
            passed.append(c)
        elif (
            c.np_likeness_score is not None
            and c.np_likeness_score >= params.np_exception_threshold
        ):
            np_exceptions.append(c)
        else:
            failed.append(c)

    return {
        "passed": passed,
        "failed": failed,
        "np_exceptions": np_exceptions,
        "passed_count": len(passed),
        "failed_count": len(failed),
        "np_exception_count": len(np_exceptions),
    }


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage1 = (run.stage_results or {}).get("stage_1", {})
    compound_ids = [UUID(cid) for cid in stage1.get("compound_ids", [])]

    db_compounds = []
    for cid in compound_ids:
        c = await compound_repo.get_compound_by_id(session, cid)
        if c:
            db_compounds.append(CompoundRecord(
                compound_id=c.compound_id,
                canonical_name=c.canonical_name,
                smiles=c.smiles,
                chembl_id=c.chembl_id,
                pubchem_cid=c.pubchem_cid,
                molecular_weight=c.molecular_weight,
                logp=c.logp,
                hbond_donors=c.hbond_donors,
                hbond_acceptors=c.hbond_acceptors,
                tpsa=c.tpsa,
                rotatable_bonds=c.rotatable_bonds,
                np_likeness_score=c.np_likeness_score,
                num_ro5_violations=c.num_ro5_violations,
            ))

    result = filter_compounds(db_compounds, config.adme)

    return {
        "passed_count": result["passed_count"],
        "failed_count": result["failed_count"],
        "np_exception_count": result["np_exception_count"],
        "passed_compound_ids": [str(c.compound_id) for c in result["passed"]],
        "np_exception_compound_ids": [str(c.compound_id) for c in result["np_exceptions"]],
        "all_active_compound_ids": [
            str(c.compound_id)
            for c in result["passed"] + result["np_exceptions"]
        ],
    }
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
uv run pytest tests/unit/test_adme.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Implement stage1_selection.py**

```python
# backend/analysis/stages/stage1_selection.py
from uuid import UUID
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories.compound_repo import get_compounds_for_plants


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}
    plant_ids = [UUID(pid) for pid in params.get("_plant_ids", [])]

    if not plant_ids:
        return {"compound_ids": [], "compound_count": 0, "error": "No plant IDs provided"}

    compounds = await get_compounds_for_plants(session, plant_ids)
    return {
        "compound_count": len(compounds),
        "compound_ids": [str(c.compound_id) for c in compounds],
        "plant_ids": [str(p) for p in plant_ids],
    }
```

- [ ] **Step 6: Commit**

```bash
git add backend/analysis/stages/stage1_selection.py backend/analysis/stages/stage2_adme.py backend/tests/unit/test_adme.py
git commit -m "feat(backend): implement stages 1 and 2 (selection and ADME filter)"
```

---

## Task 13: ChEMBL integration client

**Files:**
- Create: `backend/integrations/chembl.py`

The ChEMBL API is a standard REST API. We query by molecule ChEMBL ID, get bioactivity records, then resolve target ChEMBL IDs to gene symbols.

- [ ] **Step 1: Write integrations/chembl.py**

```python
# backend/integrations/chembl.py
import asyncio
import httpx
from dataclasses import dataclass


CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
SEMAPHORE = asyncio.Semaphore(10)  # Max concurrent requests


@dataclass
class ChemblTarget:
    chembl_id: str
    gene_symbol: str | None
    uniprot_accession: str | None
    organism: str | None
    pchembl_value: float | None


@dataclass
class ChemblBioactivity:
    molecule_chembl_id: str
    target_chembl_id: str
    pchembl_value: float | None
    target_organism: str | None
    assay_type: str | None


async def get_bioactivities(
    client: httpx.AsyncClient,
    molecule_chembl_id: str,
    min_pchembl: float = 5.0,
    human_only: bool = True,
) -> list[ChemblBioactivity]:
    """Fetch bioactivity records for one compound. Returns target ChEMBL IDs."""
    params = {
        "molecule_chembl_id": molecule_chembl_id,
        "limit": 1000,
        "offset": 0,
        "format": "json",
    }
    if human_only:
        params["target_organism"] = "Homo sapiens"

    async with SEMAPHORE:
        try:
            resp = await client.get(f"{CHEMBL_BASE}/activity.json", params=params, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

    data = resp.json()
    activities = []
    for row in data.get("activities", []):
        pchembl = row.get("pchembl_value")
        if pchembl is not None:
            try:
                pchembl = float(pchembl)
            except (TypeError, ValueError):
                pchembl = None

        if min_pchembl and (pchembl is None or pchembl < min_pchembl):
            continue

        target_chembl_id = row.get("target_chembl_id")
        if not target_chembl_id:
            continue

        activities.append(ChemblBioactivity(
            molecule_chembl_id=molecule_chembl_id,
            target_chembl_id=target_chembl_id,
            pchembl_value=pchembl,
            target_organism=row.get("target_organism"),
            assay_type=row.get("assay_type"),
        ))

    return activities


async def resolve_target(
    client: httpx.AsyncClient, target_chembl_id: str
) -> ChemblTarget | None:
    """Resolve a ChEMBL target ID to gene symbol + UniProt accession."""
    async with SEMAPHORE:
        try:
            resp = await client.get(
                f"{CHEMBL_BASE}/target/{target_chembl_id}.json",
                timeout=20,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        except httpx.HTTPError:
            return None

    data = resp.json()
    gene_symbol = None
    uniprot = None

    for component in data.get("target_components", []):
        for synonym in component.get("target_component_synonyms", []):
            if synonym.get("syn_type") == "GENE_SYMBOL":
                gene_symbol = synonym.get("component_synonym")
            if synonym.get("syn_type") == "UNIPROT":
                uniprot = synonym.get("component_synonym")

    return ChemblTarget(
        chembl_id=target_chembl_id,
        gene_symbol=gene_symbol,
        uniprot_accession=uniprot,
        organism=data.get("organism"),
        pchembl_value=None,
    )


async def get_targets_for_compounds(
    chembl_ids: list[str],
    min_pchembl: float = 5.0,
    human_only: bool = True,
) -> dict[str, list[ChemblTarget]]:
    """
    Returns a mapping: molecule_chembl_id → list of resolved ChemblTargets.
    Deduplicates targets across compounds.
    """
    target_cache: dict[str, ChemblTarget] = {}
    compound_targets: dict[str, list[ChemblTarget]] = {cid: [] for cid in chembl_ids}

    async with httpx.AsyncClient() as client:
        # Fetch all bioactivities concurrently
        tasks = [get_bioactivities(client, cid, min_pchembl, human_only) for cid in chembl_ids]
        all_bioactivities = await asyncio.gather(*tasks)

        # Collect unique target ChEMBL IDs to resolve
        unique_target_ids = set()
        for activities in all_bioactivities:
            for act in activities:
                unique_target_ids.add(act.target_chembl_id)

        # Resolve all unique targets concurrently
        resolve_tasks = [resolve_target(client, tid) for tid in unique_target_ids]
        resolved = await asyncio.gather(*resolve_tasks)
        for target in resolved:
            if target and target.gene_symbol:
                target_cache[target.chembl_id] = target

        # Build compound → targets mapping
        for cid, activities in zip(chembl_ids, all_bioactivities):
            seen_targets = set()
            for act in activities:
                target = target_cache.get(act.target_chembl_id)
                if target and target.gene_symbol not in seen_targets:
                    # Attach the max pchembl value for this compound-target pair
                    target_with_pchembl = ChemblTarget(
                        chembl_id=target.chembl_id,
                        gene_symbol=target.gene_symbol,
                        uniprot_accession=target.uniprot_accession,
                        organism=target.organism,
                        pchembl_value=act.pchembl_value,
                    )
                    compound_targets[cid].append(target_with_pchembl)
                    seen_targets.add(target.gene_symbol)

    return compound_targets
```

- [ ] **Step 2: Quick smoke test against ChEMBL (no pytest)**

Caffeine is CHEMBL113 and has well-known targets (PDE, ADORA). Run manually:
```python
# test_chembl_smoke.py — run once manually, not part of CI
import asyncio
from integrations.chembl import get_targets_for_compounds

async def main():
    results = await get_targets_for_compounds(["CHEMBL113"], min_pchembl=5.0)
    print(f"Caffeine targets: {[t.gene_symbol for t in results['CHEMBL113']]}")

asyncio.run(main())
```

Run from `backend/`:
```bash
uv run python test_chembl_smoke.py
```
Expected: prints caffeine targets including known adenosine receptors.

- [ ] **Step 3: Commit**

```bash
git add backend/integrations/chembl.py
git commit -m "feat(backend): add ChEMBL API integration client"
```

---

## Task 14: Stage 3 — Target association

**Files:**
- Modify: `backend/analysis/stages/stage3_targets.py`

- [ ] **Step 1: Implement stage3_targets.py**

```python
# backend/analysis/stages/stage3_targets.py
from uuid import UUID, uuid5, NAMESPACE_DNS
from datetime import datetime, timezone
from analysis.models import PipelineConfig, TargetRecord
from app.models.analysis import AnalysisRun
from app.models.target import Target, CompoundTarget
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import compound_repo
from integrations.chembl import get_targets_for_compounds, ChemblTarget


def _make_target_id(gene_symbol: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"target:gene:{gene_symbol.upper()}")


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage2 = (run.stage_results or {}).get("stage_2", {})
    compound_ids = [UUID(cid) for cid in stage2.get("all_active_compound_ids", [])]

    if not compound_ids:
        return {"covered": 0, "no_data": 0, "coverage_pct": 0.0, "targets": []}

    # Load compounds to get chembl_ids
    compound_records = {}
    chembl_to_compound: dict[str, UUID] = {}
    for cid in compound_ids:
        c = await compound_repo.get_compound_by_id(session, cid)
        if c:
            compound_records[cid] = c
            if c.chembl_id:
                chembl_to_compound[c.chembl_id] = cid

    # Fetch targets from ChEMBL
    chembl_ids = list(chembl_to_compound.keys())
    chembl_results: dict[str, list[ChemblTarget]] = {}
    if chembl_ids:
        chembl_results = await get_targets_for_compounds(
            chembl_ids,
            min_pchembl=config.target.min_pchembl,
            human_only=config.target.human_only,
        )

    # Build target → compound_ids mapping; upsert targets into DB
    target_compound_map: dict[str, list[UUID]] = {}
    target_info: dict[str, ChemblTarget] = {}

    for chembl_mol_id, targets in chembl_results.items():
        compound_id = chembl_to_compound[chembl_mol_id]
        for t in targets:
            if not t.gene_symbol:
                continue
            gene = t.gene_symbol.upper()
            if gene not in target_compound_map:
                target_compound_map[gene] = []
                target_info[gene] = t
            target_compound_map[gene].append(compound_id)

    # Upsert Target rows
    now = datetime.now(timezone.utc)
    for gene, t in target_info.items():
        target_id = _make_target_id(gene)
        existing = await session.get(Target, target_id)
        if not existing:
            new_target = Target(
                target_id=target_id,
                canonical_key=f"chembl:{t.chembl_id}",
                gene_symbol=gene,
                uniprot_accession=t.uniprot_accession,
                organism_tax_id=9606,
                retrieved_at=now,
            )
            session.add(new_target)

    await session.commit()

    # Upsert CompoundTarget rows
    for gene, compound_id_list in target_compound_map.items():
        target_id = _make_target_id(gene)
        t = target_info[gene]
        for cid in set(compound_id_list):
            ct_id = uuid5(NAMESPACE_DNS, f"ct:{cid}:{target_id}")
            existing = await session.get(CompoundTarget, ct_id)
            if not existing:
                session.add(CompoundTarget(
                    compound_target_id=ct_id,
                    compound_id=cid,
                    target_id=target_id,
                    prediction_method="chembl_bioactivity",
                    evidence_type="experimental",
                    pchembl_value=t.pchembl_value,
                    retrieved_at=now,
                ))
    await session.commit()

    covered = len(set(chembl_to_compound.values()) & {
        cid for cids in target_compound_map.values() for cid in cids
    })
    no_data = len(compound_ids) - covered
    coverage_pct = round(covered / len(compound_ids) * 100, 1) if compound_ids else 0.0

    return {
        "covered": covered,
        "no_data": no_data,
        "coverage_pct": coverage_pct,
        "target_count": len(target_compound_map),
        "target_gene_symbols": list(target_compound_map.keys()),
        "target_compound_map": {
            gene: [str(cid) for cid in cids]
            for gene, cids in target_compound_map.items()
        },
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/analysis/stages/stage3_targets.py
git commit -m "feat(backend): implement stage 3 (ChEMBL target association)"
```

---

## Task 15: Open Targets integration and Stage 4

**Files:**
- Create: `backend/integrations/open_targets.py`
- Modify: `backend/analysis/stages/stage4_disease_targets.py`

Stage 4 primary source is the `disease_targets` DB table (populated by ETL). Open Targets API is the fallback.

- [ ] **Step 1: Write integrations/open_targets.py**

```python
# backend/integrations/open_targets.py
import httpx
from dataclasses import dataclass

OT_BASE = "https://api.platform.opentargets.org/api/v4"


@dataclass
class OtAssociation:
    gene_symbol: str
    ensembl_id: str
    score: float


async def get_disease_targets(
    efo_id: str, min_score: float = 0.3, limit: int = 500
) -> list[OtAssociation]:
    """
    Fetch gene-disease associations from Open Targets.
    efo_id is the EFO/ontology ID (e.g., 'EFO_0000400' for diabetes mellitus).
    """
    query = """
    query DiseaseTargets($efoId: String!, $size: Int!) {
      disease(efoId: $efoId) {
        associatedTargets(page: {index: 0, size: $size}) {
          rows {
            target {
              approvedSymbol
              id
            }
            score
          }
        }
      }
    }
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{OT_BASE}/graphql",
                json={"query": query, "variables": {"efoId": efo_id, "size": limit}},
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

    data = resp.json().get("data", {})
    disease_data = data.get("disease", {})
    if not disease_data:
        return []

    rows = disease_data.get("associatedTargets", {}).get("rows", [])
    return [
        OtAssociation(
            gene_symbol=row["target"]["approvedSymbol"],
            ensembl_id=row["target"]["id"],
            score=row["score"],
        )
        for row in rows
        if row["score"] >= min_score
    ]
```

- [ ] **Step 2: Implement stage4_disease_targets.py**

```python
# backend/analysis/stages/stage4_disease_targets.py
from uuid import UUID
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import disease_repo


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    params = run.parameters or {}
    disease_ids = [UUID(did) for did in params.get("_disease_ids", [])]

    all_targets: dict[str, dict] = {}

    for did in disease_ids:
        disease = await disease_repo.get_disease_by_id(session, did)
        if not disease:
            continue

        # Primary: query DB (populated by ETL)
        db_targets = await disease_repo.get_targets_for_disease(
            session, did, min_score=config.disease_targets.min_score
        )

        if db_targets:
            for target, score in db_targets:
                gene = (target.gene_symbol or "").upper()
                if gene and gene not in all_targets:
                    all_targets[gene] = {
                        "gene_symbol": gene,
                        "uniprot_accession": target.uniprot_accession,
                        "score": score,
                        "disease_name": disease.disease_name,
                        "source": "db_cache",
                    }
        else:
            # Fallback: Open Targets API
            from integrations.open_targets import get_disease_targets
            ontology_id = disease.ontology_id or ""
            ot_targets = await get_disease_targets(
                ontology_id, min_score=config.disease_targets.min_score
            )
            for t in ot_targets:
                gene = t.gene_symbol.upper()
                if gene not in all_targets:
                    all_targets[gene] = {
                        "gene_symbol": gene,
                        "uniprot_accession": None,
                        "score": t.score,
                        "disease_name": disease.disease_name,
                        "source": "open_targets_api",
                    }

    return {
        "disease_target_count": len(all_targets),
        "disease_gene_symbols": list(all_targets.keys()),
        "targets": list(all_targets.values()),
    }
```

- [ ] **Step 3: Commit**

```bash
git add backend/integrations/open_targets.py backend/analysis/stages/stage4_disease_targets.py
git commit -m "feat(backend): add Open Targets integration and stage 4 (disease targets)"
```

---

## Task 16: Stage 5 — Target overlap (TDD)

**Files:**
- Create: `backend/tests/unit/test_overlap.py`
- Modify: `backend/analysis/stages/stage5_overlap.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_overlap.py
from analysis.stages.stage5_overlap import compute_overlap


def test_basic_overlap():
    compound_genes = {"TP53", "AKT1", "TNF", "EGFR"}
    disease_genes = {"AKT1", "TNF", "BRCA1"}
    result = compute_overlap(compound_genes, disease_genes)
    assert set(result["overlap"]) == {"AKT1", "TNF"}
    assert result["overlap_count"] == 2
    assert result["compound_only_count"] == 2
    assert result["disease_only_count"] == 1


def test_no_overlap():
    result = compute_overlap({"TP53"}, {"BRCA1"})
    assert result["overlap_count"] == 0
    assert result["jaccard"] == 0.0


def test_jaccard():
    # Overlap=2, union=4: jaccard=0.5
    result = compute_overlap({"A", "B"}, {"B", "C"})
    assert abs(result["jaccard"] - (1/3)) < 0.001  # union={A,B,C}=3, overlap=1


def test_p_value_significant():
    # Large overlap from small universe should be significant
    result = compute_overlap(
        {"TP53", "AKT1", "TNF", "EGFR", "VEGFA"},
        {"TP53", "AKT1", "TNF", "EGFR", "BRCA1"},
        population_size=20000,
    )
    assert result["p_value"] < 0.05


def test_empty_inputs():
    result = compute_overlap(set(), {"BRCA1"})
    assert result["overlap_count"] == 0
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
uv run pytest tests/unit/test_overlap.py -v
```
Expected: `ImportError` — `compute_overlap` not defined.

- [ ] **Step 3: Implement stage5_overlap.py**

```python
# backend/analysis/stages/stage5_overlap.py
from scipy.stats import hypergeom
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession

HUMAN_PROTEOME_SIZE = 20_000  # Approximate number of human protein-coding genes


def compute_overlap(
    compound_genes: set[str],
    disease_genes: set[str],
    population_size: int = HUMAN_PROTEOME_SIZE,
) -> dict:
    overlap = compound_genes & disease_genes
    union = compound_genes | disease_genes

    overlap_count = len(overlap)
    union_count = len(union)
    compound_only_count = len(compound_genes) - overlap_count
    disease_only_count = len(disease_genes) - overlap_count

    jaccard = overlap_count / union_count if union_count > 0 else 0.0

    # Fisher's exact / hypergeometric test:
    # P(X >= k | N=population, K=disease_genes, n=compound_genes)
    p_value = 1.0
    if overlap_count > 0 and compound_genes and disease_genes:
        rv = hypergeom(
            M=population_size,
            n=len(disease_genes),
            N=len(compound_genes),
        )
        p_value = float(rv.sf(overlap_count - 1))

    return {
        "overlap": sorted(overlap),
        "overlap_count": overlap_count,
        "compound_only_count": compound_only_count,
        "disease_only_count": disease_only_count,
        "jaccard": round(jaccard, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "venn": {
            "compound_only": compound_only_count,
            "overlap": overlap_count,
            "disease_only": disease_only_count,
        },
    }


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage3 = (run.stage_results or {}).get("stage_3", {})
    stage4 = (run.stage_results or {}).get("stage_4", {})

    compound_genes = set(stage3.get("target_gene_symbols", []))
    disease_genes = set(stage4.get("disease_gene_symbols", []))

    result = compute_overlap(compound_genes, disease_genes)
    return result
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
uv run pytest tests/unit/test_overlap.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/stages/stage5_overlap.py backend/tests/unit/test_overlap.py
git commit -m "feat(backend): implement stage 5 (target overlap with statistical test)"
```

---

## Task 17: Approve/reject endpoints

**Files:**
- Modify: `backend/app/routers/analyses.py`

- [ ] **Step 1: Add approve and reject routes to analyses.py**

Add these routes to the existing `analyses.py` (after the existing `get_analysis` route):

```python
@router.post("/{analysis_id}/approve")
async def approve_stage(
    analysis_id: UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if "_awaiting_approval" not in run.status:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis is not awaiting approval (current status: {run.status})"
        )

    # Parse current stage from status like "stage_3_awaiting_approval"
    current_stage = int(run.status.split("_")[1])
    next_stage = current_stage + 1

    if next_stage > 8:
        await analysis_repo.update_run_status(
            session, analysis_id, status="complete", completed=True
        )
        return {"status": "complete"}

    background_tasks.add_task(
        run_stage, analysis_id, next_stage, async_session_factory
    )
    return {"status": f"stage_{next_stage}_starting", "next_stage": next_stage}


@router.post("/{analysis_id}/reject")
async def reject_stage(
    analysis_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if "_awaiting_approval" not in run.status:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis is not awaiting approval (current status: {run.status})"
        )

    # Revert to previous stage's awaiting state (let user re-run with different params)
    current_stage = int(run.status.split("_")[1])
    await analysis_repo.update_run_status(
        session, analysis_id,
        status=f"stage_{current_stage}_rejected",
    )
    return {"status": f"stage_{current_stage}_rejected"}


@router.delete("/{analysis_id}")
async def delete_analysis(analysis_id: UUID, session: AsyncSession = Depends(get_session)):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")
    await session.delete(run)
    await session.commit()
    return {"deleted": True}
```

Also add this import at the top of analyses.py:
```python
from analysis.pipeline import run_stage
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/analyses.py
git commit -m "feat(backend): add approve and reject stage endpoints"
```

---

## Task 18: STRING DB integration and Stage 6

**Files:**
- Create: `backend/integrations/stringdb.py`
- Modify: `backend/analysis/stages/stage6_ppi.py`

- [ ] **Step 1: Write integrations/stringdb.py**

```python
# backend/integrations/stringdb.py
import httpx
from dataclasses import dataclass

STRING_BASE = "https://string-db.org/api/json"
SPECIES_HUMAN = 9606


@dataclass
class PpiEdgeData:
    gene_a: str
    gene_b: str
    combined_score: float
    experimental_score: float
    textmining_score: float
    coexpression_score: float


async def get_ppi_network(
    gene_symbols: list[str],
    min_confidence: float = 0.4,
) -> list[PpiEdgeData]:
    """
    Fetch PPI edges for a list of gene symbols from STRING DB.
    min_confidence: 0.15=low, 0.40=medium, 0.70=high, 0.90=highest
    """
    if not gene_symbols:
        return []

    identifiers = "\r".join(gene_symbols)
    params = {
        "identifiers": identifiers,
        "species": SPECIES_HUMAN,
        "required_score": int(min_confidence * 1000),  # STRING uses 0-1000
        "caller_identity": "herbaflow_thesis",
        "format": "json",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{STRING_BASE}/network",
                data=params,
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

    edges = []
    for row in resp.json():
        gene_a = row.get("preferredName_A", "")
        gene_b = row.get("preferredName_B", "")
        if not gene_a or not gene_b or gene_a == gene_b:
            continue
        combined = float(row.get("score", 0))
        if combined < min_confidence:
            continue
        edges.append(PpiEdgeData(
            gene_a=gene_a.upper(),
            gene_b=gene_b.upper(),
            combined_score=combined,
            experimental_score=float(row.get("escore", 0)),
            textmining_score=float(row.get("tscore", 0)),
            coexpression_score=float(row.get("coexpression_score", 0)),
        ))

    return edges
```

- [ ] **Step 2: Implement stage6_ppi.py**

```python
# backend/analysis/stages/stage6_ppi.py
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from integrations.stringdb import get_ppi_network


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage5 = (run.stage_results or {}).get("stage_5", {})
    overlapping_genes = stage5.get("overlap", [])

    if not overlapping_genes:
        return {"node_count": 0, "edge_count": 0, "nodes": [], "edges": []}

    edges = await get_ppi_network(
        overlapping_genes, min_confidence=config.ppi.min_confidence
    )

    # Build Cytoscape.js-compatible network JSON
    all_genes = set()
    edge_list = []
    for e in edges:
        all_genes.add(e.gene_a)
        all_genes.add(e.gene_b)
        edge_list.append({
            "source": e.gene_a,
            "target": e.gene_b,
            "combined_score": e.combined_score,
            "experimental_score": e.experimental_score,
        })

    nodes = [{"id": g, "label": g} for g in sorted(all_genes)]

    return {
        "node_count": len(nodes),
        "edge_count": len(edge_list),
        "nodes": nodes,
        "edges": edge_list,
        "cytoscape": {
            "elements": {
                "nodes": [{"data": n} for n in nodes],
                "edges": [
                    {"data": {"source": e["source"], "target": e["target"], "weight": e["combined_score"]}}
                    for e in edge_list
                ],
            }
        },
    }
```

- [ ] **Step 3: Commit**

```bash
git add backend/integrations/stringdb.py backend/analysis/stages/stage6_ppi.py
git commit -m "feat(backend): add STRING DB integration and stage 6 (PPI network)"
```

---

## Task 19: Stage 7 — Hub gene analysis (TDD)

**Files:**
- Create: `backend/tests/unit/test_centrality.py`
- Modify: `backend/analysis/stages/stage7_hub_genes.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_centrality.py
import networkx as nx
from analysis.stages.stage7_hub_genes import compute_hub_genes


def make_star_graph() -> nx.Graph:
    """Star graph: node 'center' connected to 4 leaves. Center is clearly the hub."""
    G = nx.Graph()
    G.add_edges_from([("center", "a"), ("center", "b"), ("center", "c"), ("center", "d")])
    return G


def test_hub_identified():
    G = make_star_graph()
    result = compute_hub_genes(G, top_n=5)
    # Center has degree 4, others have degree 1 — center must be top-ranked
    assert result["ranked"][0]["gene_symbol"] == "center"


def test_all_4_metrics_present():
    G = make_star_graph()
    result = compute_hub_genes(G, top_n=5)
    top = result["ranked"][0]
    assert "degree" in top
    assert "betweenness" in top
    assert "closeness" in top
    assert "eigenvector" in top


def test_hub_bottleneck_flagged():
    G = make_star_graph()
    result = compute_hub_genes(G, top_n=5)
    center = next(r for r in result["ranked"] if r["gene_symbol"] == "center")
    # Center has both high degree and high betweenness — should be hub-bottleneck
    assert center["is_hub"] is True
    assert center["is_hub_bottleneck"] is True


def test_top_n_respected():
    G = nx.complete_graph(10)
    nx.relabel_nodes(G, {i: f"gene_{i}" for i in range(10)}, copy=False)
    result = compute_hub_genes(G, top_n=3)
    assert len(result["ranked"]) == 3


def test_empty_graph():
    G = nx.Graph()
    result = compute_hub_genes(G, top_n=20)
    assert result["ranked"] == []
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
uv run pytest tests/unit/test_centrality.py -v
```

- [ ] **Step 3: Implement stage7_hub_genes.py**

```python
# backend/analysis/stages/stage7_hub_genes.py
import statistics
import networkx as nx
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession


def compute_hub_genes(G: nx.Graph, top_n: int = 20) -> dict:
    if len(G.nodes) == 0:
        return {"ranked": [], "hub_degree_threshold": 0, "hub_betweenness_threshold": 0}

    degrees = dict(G.degree())

    # Handle single-node graph (centrality functions require >= 1 node)
    if len(G.nodes) == 1:
        node = list(G.nodes)[0]
        return {
            "ranked": [{"gene_symbol": node, "degree": 0, "betweenness": 0.0,
                        "closeness": 0.0, "eigenvector": 0.0,
                        "is_hub": False, "is_hub_bottleneck": False, "rank": 1}],
            "hub_degree_threshold": 0,
            "hub_betweenness_threshold": 0,
        }

    betweenness = nx.betweenness_centrality(G, normalized=True)
    closeness = nx.closeness_centrality(G)
    try:
        eigenvector = nx.eigenvector_centrality(G, max_iter=1000, tol=1e-6)
    except nx.PowerIterationFailedConvergence:
        eigenvector = {n: 0.0 for n in G.nodes}

    degree_values = list(degrees.values())
    bet_values = list(betweenness.values())

    if len(degree_values) >= 2:
        deg_mean = statistics.mean(degree_values)
        deg_std = statistics.stdev(degree_values)
        hub_degree_threshold = deg_mean + 2 * deg_std

        bet_mean = statistics.mean(bet_values)
        bet_std = statistics.stdev(bet_values)
        hub_bet_threshold = bet_mean + 2 * bet_std
    else:
        hub_degree_threshold = 0
        hub_bet_threshold = 0

    ranked = []
    for node in G.nodes:
        deg = degrees[node]
        bet = betweenness[node]
        is_hub = deg >= hub_degree_threshold
        is_hub_bottleneck = is_hub and bet >= hub_bet_threshold
        ranked.append({
            "gene_symbol": node,
            "degree": deg,
            "betweenness": round(bet, 6),
            "closeness": round(closeness[node], 6),
            "eigenvector": round(eigenvector[node], 6),
            "is_hub": is_hub,
            "is_hub_bottleneck": is_hub_bottleneck,
        })

    ranked.sort(key=lambda x: x["degree"], reverse=True)
    ranked = ranked[:top_n]
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return {
        "ranked": ranked,
        "hub_degree_threshold": round(hub_degree_threshold, 2),
        "hub_betweenness_threshold": round(hub_bet_threshold, 6) if isinstance(hub_bet_threshold, float) else 0,
    }


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage6 = (run.stage_results or {}).get("stage_6", {})
    edges = stage6.get("edges", [])

    G = nx.Graph()
    for edge in edges:
        G.add_edge(edge["source"], edge["target"], weight=edge.get("combined_score", 1.0))

    result = compute_hub_genes(G, top_n=config.hub_genes.top_n)

    # Write to target_rankings table
    from uuid import uuid4
    from datetime import datetime, timezone
    from app.models.analysis import TargetRanking
    from app.models.target import Target
    from sqlmodel import select

    for entry in result["ranked"]:
        gene = entry["gene_symbol"]
        target_result = await session.exec(select(Target).where(Target.gene_symbol == gene))
        target = target_result.first()
        if not target:
            continue
        ranking = TargetRanking(
            ranking_id=uuid4(),
            analysis_id=run.analysis_id,
            target_id=target.target_id,
            degree_centrality=float(entry["degree"]),
            betweenness_centrality=entry["betweenness"],
            closeness_centrality=entry["closeness"],
            eigenvector_centrality=entry["eigenvector"],
            rank_position=entry["rank"],
            created_at=datetime.now(timezone.utc),
        )
        session.add(ranking)

    await session.commit()
    return result
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
uv run pytest tests/unit/test_centrality.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/stages/stage7_hub_genes.py backend/tests/unit/test_centrality.py
git commit -m "feat(backend): implement stage 7 (hub gene centrality analysis)"
```

---

## Task 20: g:Profiler integration and Stage 8

**Files:**
- Create: `backend/integrations/gprofiler.py`
- Modify: `backend/analysis/stages/stage8_enrichment.py`

- [ ] **Step 1: Write integrations/gprofiler.py**

```python
# backend/integrations/gprofiler.py
import httpx
from dataclasses import dataclass

GPROFILER_BASE = "https://biit.cs.ut.ee/gprofiler/api"


@dataclass
class EnrichmentResult:
    source: str          # 'GO:BP', 'GO:MF', 'GO:CC', 'KEGG'
    term_id: str
    term_name: str
    p_value: float
    fdr: float
    intersection_size: int
    term_size: int
    query_size: int
    genes: list[str]


async def run_enrichment(
    gene_symbols: list[str],
    sources: list[str] | None = None,
    fdr_threshold: float = 0.05,
    organism: str = "hsapiens",
) -> list[EnrichmentResult]:
    """
    Run GO and KEGG pathway enrichment via g:Profiler.
    Returns results filtered to fdr <= fdr_threshold.
    """
    if not gene_symbols:
        return []

    if sources is None:
        sources = ["GO:BP", "GO:MF", "GO:CC", "KEGG"]

    payload = {
        "organism": organism,
        "query": gene_symbols,
        "sources": sources,
        "user_threshold": fdr_threshold,
        "correction_method": "fdr_bh",
        "domain_scope": "annotated",
        "no_evidences": False,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{GPROFILER_BASE}/gost/profile/",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

    data = resp.json()
    results_raw = data.get("result", [])

    results = []
    for row in results_raw:
        if row.get("significant") is False:
            continue
        fdr = row.get("p_value", 1.0)  # g:Profiler returns corrected p in 'p_value'
        if fdr > fdr_threshold:
            continue
        results.append(EnrichmentResult(
            source=row.get("source", ""),
            term_id=row.get("native", ""),
            term_name=row.get("name", ""),
            p_value=row.get("p_value", 1.0),
            fdr=fdr,
            intersection_size=row.get("intersection_size", 0),
            term_size=row.get("term_size", 0),
            query_size=row.get("query_size", 0),
            genes=row.get("intersections", []),
        ))

    return results
```

- [ ] **Step 2: Implement stage8_enrichment.py**

```python
# backend/analysis/stages/stage8_enrichment.py
from analysis.models import PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from integrations.gprofiler import run_enrichment


def _group_by_source(results) -> dict:
    grouped = {}
    for r in results:
        source = r.source
        if source not in grouped:
            grouped[source] = []
        grouped[source].append({
            "term_id": r.term_id,
            "term_name": r.term_name,
            "p_value": round(r.p_value, 8),
            "fdr": round(r.fdr, 8),
            "intersection_size": r.intersection_size,
            "term_size": r.term_size,
            "genes": r.genes,
        })
    # Sort each group by FDR ascending, take top 20
    for source in grouped:
        grouped[source] = sorted(grouped[source], key=lambda x: x["fdr"])[:20]
    return grouped


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage7 = (run.stage_results or {}).get("stage_7", {})
    hub_genes = [r["gene_symbol"] for r in stage7.get("ranked", [])]

    if not hub_genes:
        return {"total_significant": 0, "go_bp": [], "go_mf": [], "go_cc": [], "kegg": []}

    results = await run_enrichment(
        gene_symbols=hub_genes,
        sources=config.enrichment.sources,
        fdr_threshold=config.enrichment.fdr_threshold,
    )

    grouped = _group_by_source(results)
    return {
        "total_significant": len(results),
        "go_bp": grouped.get("GO:BP", []),
        "go_mf": grouped.get("GO:MF", []),
        "go_cc": grouped.get("GO:CC", []),
        "kegg": grouped.get("KEGG", []),
        "hub_genes_queried": hub_genes,
    }
```

- [ ] **Step 3: Commit**

```bash
git add backend/integrations/gprofiler.py backend/analysis/stages/stage8_enrichment.py
git commit -m "feat(backend): add g:Profiler integration and stage 8 (enrichment analysis)"
```

---

## Task 21: Export endpoint

**Files:**
- Modify: `backend/app/routers/analyses.py`

- [ ] **Step 1: Add export route**

Add to `analyses.py`:

```python
import csv
import io
import json
from fastapi.responses import StreamingResponse


@router.get("/{analysis_id}/export/{stage}")
async def export_stage_results(
    analysis_id: UUID,
    stage: str,
    format: str = "json",  # 'json' | 'csv'
    session: AsyncSession = Depends(get_session),
):
    run = await analysis_repo.get_run(session, analysis_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stage_key = f"stage_{stage}" if not stage.startswith("stage_") else stage
    stage_data = (run.stage_results or {}).get(stage_key)
    if stage_data is None:
        raise HTTPException(status_code=404, detail=f"Stage {stage} results not found")

    if format == "json":
        content = json.dumps(stage_data, indent=2)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_{stage_key}.json"},
        )

    # CSV: flatten for tabular stages (stage 7 hub genes is the most useful)
    if stage_key == "stage_7":
        rows = stage_data.get("ranked", [])
        if rows:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_hub_genes.csv"},
            )

    # Default: return JSON even when csv requested
    content = json.dumps(stage_data, indent=2)
    return StreamingResponse(
        io.StringIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={run.analysis_name}_{stage_key}.json"},
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/analyses.py
git commit -m "feat(backend): add stage result export endpoint (JSON and CSV)"
```

---

## Task 22: Conftest and integration smoke test

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_api.py`

- [ ] **Step 1: Write conftest.py**

```python
# backend/tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

- [ ] **Step 2: Write integration test**

```python
# backend/tests/integration/test_api.py
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_list_diseases_returns_10(client):
    resp = await client.get("/diseases")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 10  # 10 curated diseases from ETL


@pytest.mark.asyncio
async def test_list_plants_has_compounds(client):
    resp = await client.get("/plants")
    assert resp.status_code == 200
    plants = resp.json()
    assert len(plants) > 0
    # At least one plant should have compounds
    assert any(p["compound_count"] > 0 for p in plants)


@pytest.mark.asyncio
async def test_create_analysis_returns_pending(client):
    # Get a real plant_id to use
    plants_resp = await client.get("/plants?limit=1")
    plant_id = plants_resp.json()[0]["plant_id"]

    diseases_resp = await client.get("/diseases")
    disease_id = diseases_resp.json()[0]["disease_id"]

    resp = await client.post("/analyses", json={
        "name": "Integration Test Run",
        "mode": "guided",
        "plant_ids": [plant_id],
        "disease_ids": [disease_id],
        "parameters": {},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert "analysis_id" in data
```

- [ ] **Step 3: Run integration tests (requires live Supabase connection)**

```bash
uv run pytest tests/integration/ -v
```
Expected: all tests pass against real Supabase data.

- [ ] **Step 4: Run full unit test suite**

```bash
uv run pytest tests/unit/ -v
```
Expected: all unit tests pass.

- [ ] **Step 5: Final commit**

```bash
git add backend/tests/
git commit -m "test(backend): add unit and integration tests"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task covering it |
|---|---|
| FastAPI app + CORS | Task 6 |
| SQLModel models for all tables | Tasks 4–5 |
| DB migrations (3 migrations) | Task 3 |
| GET /plants, /compounds, /diseases | Task 8 |
| POST /analyses + status polling | Task 10 |
| Stage 1 compound selection | Task 12 |
| Stage 2 ADME filter + NP exception rule | Task 12 |
| Stage 3 ChEMBL targets + STITCH fallback | Task 13–14 |
| Stage 4 disease targets + OT fallback | Task 15 |
| Stage 5 target overlap + Fisher's test | Task 16 |
| Guided mode approve/reject | Task 17 |
| Stage 6 STRING DB PPI | Task 18 |
| Stage 7 all 4 centrality + hub-bottleneck | Task 19 |
| Stage 8 g:Profiler enrichment | Task 20 |
| Export endpoints (CSV/JSON) | Task 21 |

**Note on STITCH:** The plan references STITCH as Stage 3 fallback but the implementation in Task 14 uses STITCH as a stub (`integrations/stitch.py` not yet implemented). For the first working version, only ChEMBL is active. STITCH integration (downloading ~4GB file, loading into SQLite, querying by pubchem_cid) can be added as a follow-up task when needed.

**Note on `analysis_repo.py` missing `plant_repo.py`:** `GET /plants` uses a direct `select(Plant)` in the router for simplicity. A proper `plant_repo.py` can be added alongside the compound/disease repos if the plant queries grow in complexity.
