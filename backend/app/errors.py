"""Human-readable API error messages.

All HTTPException detail fields must use constants from this module (or other
literal strings) — never raw exception text such as str(e) or str(exc).
Raw exception details are logged server-side at ERROR level.
"""

# ---------------------------------------------------------------------------
# External service errors
# ---------------------------------------------------------------------------

PUBCHEM_UNAVAILABLE = (
    "PubChem is temporarily unavailable. Please try again in a few minutes."
)
PUBCHEM_VALIDATION_FAILED = (
    "Could not validate one or more compounds with PubChem. "
    "Check that your SMILES or compound identifiers are valid."
)
UNIPROT_UNAVAILABLE = (
    "UniProt is temporarily unavailable. Please try again in a few minutes."
)
UNIPROT_TARGET_NOT_FOUND = (
    "The gene symbol or UniProt accession was not found as a human protein. "
    "Verify the identifier and try again."
)
UNIPROT_VALIDATION_FAILED = (
    "Could not validate the target with UniProt. "
    "Check that the gene symbol or UniProt accession is correct."
)
CHEMBL_UNAVAILABLE = (
    "ChEMBL is temporarily unavailable. Please try again in a few minutes."
)
STRING_UNAVAILABLE = (
    "STRING-DB is temporarily unavailable. Please try again in a few minutes."
)
GPROFILER_UNAVAILABLE = (
    "g:Profiler is temporarily unavailable. Please try again in a few minutes."
)
OPEN_TARGETS_UNAVAILABLE = (
    "Open Targets is temporarily unavailable. Please try again in a few minutes."
)
PUBCHEM_BIOASSAY_UNAVAILABLE = (
    "PubChem BioAssay is temporarily unavailable. Please try again in a few minutes."
)

# ---------------------------------------------------------------------------
# Analysis / pipeline entity errors
# ---------------------------------------------------------------------------

ANALYSIS_NOT_FOUND = "Analysis not found."
COMPOUND_NOT_FOUND = "Compound not found in this analysis."
TARGET_NOT_FOUND = "Target not found in this analysis."
STAGE_NOT_READY = "This stage has not been run yet."
INVALID_STAGE = "Invalid stage number. Must be between 1 and 8."

# ---------------------------------------------------------------------------
# Conflict errors
# ---------------------------------------------------------------------------

TARGET_ALREADY_EXISTS = (
    "This target already exists in the stage results. "
    "Remove it first if you want to replace it."
)
