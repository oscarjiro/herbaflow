"""Language-neutral contracts shared with the frontend (see /shared/contracts)."""
import json
from pathlib import Path

# backend/app/contracts.py -> parents[2] is the repo root.
_CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "shared" / "contracts"

_analysis = json.loads((_CONTRACTS_DIR / "analysis.json").read_text(encoding="utf-8"))

# Allowed values for analysis_runs.mode. Single source of truth; the Pydantic
# field below and the DB CHECK are both verified against this by tests.
ANALYSIS_MODES: tuple[str, ...] = tuple(_analysis["analysis_mode"])

# Pipeline parameter groups -> set of allowed field names. Single source of truth
# shared with the frontend Zod schema and verified against the AnalysisParameters
# Pydantic model and the PipelineConfig dataclass by tests.
PIPELINE_PARAM_FIELDS: dict[str, set[str]] = {
    group: set(fields)
    for group, fields in _analysis["pipeline_parameters"].items()
}

# Allowed values for a stage result's `state` field. Single source of truth shared
# with the frontend and verified against the analysis.stage_state constants by tests.
STAGE_STATES: tuple[str, ...] = tuple(_analysis["stage_state"])
