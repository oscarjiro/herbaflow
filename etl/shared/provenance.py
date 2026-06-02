# etl/shared/provenance.py
"""Single source of truth for per-row source deep-link URLs.

Every entity and link row's source_url derives here so the per-module build_canonical
stages and the backend twin cannot drift. Contract:
.superpowers/specs/2026-06-02-s3-deep-link-provenance-design.md and docs/database.md.

Rules:
- One pure builder per source; inputs in, URL str out (or None when no usable id).
- build_source_url(source_name, **ids) dispatches by source_name (case-insensitive).
- resolve_source_url(source_name, base_url, **ids) = build_source_url(...) or base_url.

stdlib-only (no pandas) so it is importable from any step or the backend twin.
"""
from __future__ import annotations


def _clean(value: object) -> str:
    return str(value or "").strip()


# --- Per-source deep-link builders (None when the id is absent) ---

def gbif_species_url(usage_key: object) -> str | None:
    key = _clean(usage_key)
    return f"https://www.gbif.org/species/{key}" if key else None


def pubchem_compound_url(cid: object) -> str | None:
    c = _clean(cid)
    return f"https://pubchem.ncbi.nlm.nih.gov/compound/{c}" if c else None


def chembl_compound_url(chembl_id: object) -> str | None:
    cid = _clean(chembl_id)
    return f"https://www.ebi.ac.uk/chembl/compound_report_card/{cid}" if cid else None


def uniprot_url(accession: object) -> str | None:
    acc = _clean(accession)
    return f"https://www.uniprot.org/uniprotkb/{acc}/entry" if acc else None


def opentargets_target_url(ensembl_id: object) -> str | None:
    ens = _clean(ensembl_id)
    return f"https://platform.opentargets.org/target/{ens}" if ens else None


def opentargets_target_assoc_url(ensembl_id: object) -> str | None:
    ens = _clean(ensembl_id)
    return f"https://platform.opentargets.org/target/{ens}/associations" if ens else None


def opentargets_evidence_url(ensembl_id: object, efo_id: object) -> str | None:
    """Precise OT evidence page when EFO is present; else the target associations page."""
    ens = _clean(ensembl_id)
    efo = _clean(efo_id).replace(":", "_")  # OT path form: EFO_0000270
    if not ens:
        return None
    if efo:
        return f"https://platform.opentargets.org/evidence/{ens}/{efo}"
    return opentargets_target_assoc_url(ens)


def knapsack_metabolite_url(c_id: object) -> str | None:
    cid = _clean(c_id)
    return f"http://www.knapsackfamily.com/knapsack_core/information.php?word={cid}" if cid else None


_DISEASE_ONTOLOGY = {
    "doid": "https://disease-ontology.org/?id={id}",
    "disease ontology": "https://disease-ontology.org/?id={id}",
    "mesh": "https://meshb.nlm.nih.gov/record/ui?ui={id}",
}


def disease_ontology_url(ontology_source: object, ontology_id: object) -> str | None:
    src = _clean(ontology_source).lower()
    oid = _clean(ontology_id)
    template = _DISEASE_ONTOLOGY.get(src)
    if not (template and oid):
        return None
    if src in ("doid", "disease ontology"):
        # DO site needs the colon CURIE (DOID:9352); stored ids use the OBO underscore form.
        oid = oid.replace("_", ":")
    return template.format(id=oid)


# --- Dispatcher + fallback (used by tests and the backend twin) ---

def build_source_url(source_name: object, **ids: object) -> str | None:
    name = _clean(source_name).lower()
    if name == "gbif":
        return gbif_species_url(ids.get("gbif_usage_key"))
    if name == "pubchem":
        return pubchem_compound_url(ids.get("pubchem_cid"))
    if name == "chembl":
        return chembl_compound_url(ids.get("chembl_id"))
    if name == "uniprot":
        return uniprot_url(ids.get("uniprot_accession"))
    if name in ("open targets", "opentargets"):
        return opentargets_target_url(ids.get("ensembl_id"))
    if name == "knapsack":
        return knapsack_metabolite_url(ids.get("c_id"))
    if name in ("doid", "disease ontology", "mesh"):
        return disease_ontology_url(source_name, ids.get("ontology_id"))
    return None


def resolve_source_url(source_name: object, base_url: object, **ids: object) -> str:
    return build_source_url(source_name, **ids) or _clean(base_url)
