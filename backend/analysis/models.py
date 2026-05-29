from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdmeParams:
    """
    ADME screening parameters for compound filtering.

    Lipinski RO5 (Lipinski et al., Adv. Drug Deliv. Rev. 23:3-25, 1997):
      Empirical thresholds for oral bioavailability of drug-like molecules.
      Note: designed for synthetic compounds; many natural products violate RO5.
      NP exception (np_exception_threshold) compensates for this limitation.

    Veber rules (Veber et al., J. Med. Chem. 45:2615-2623, 2002):
      Additional oral permeability criteria based on TPSA and rotatable bonds.

    NP exception (Ertl & Schuffenhauer, J. Nat. Prod. 71:951-959, 2008):
      Compounds with NP-likeness score >= threshold bypass RO5/Veber filters.
      Threshold 0.5 captures compounds with strong natural-product character.

    PAINS (Baell & Holloway, J. Med. Chem. 53:2719-2740, 2010):
      Not applied as a hard filter (apply_pains=False); NP pipeline targets
      computational target prediction, not biochemical assay screening.
    """
    max_mw: float = 500.0
    max_logp: float = 5.0
    max_hbd: int = 5
    max_hba: int = 10
    max_tpsa: float = 140.0
    max_rotatable_bonds: int = 10
    apply_veber: bool = True
    apply_pains: bool = False
    np_exception_threshold: float = 0.5
    apply_adme_to_manual: bool = True
    # When False, compounds with source="user_provided" bypass Lipinski/Veber
    # screening and are included unconditionally with adme_pass=True.
    # Scientific basis: Lipinski CA et al. Adv Drug Deliv Rev. 2001.
    # Pre-screened compounds from published ADME studies should not be re-filtered.


@dataclass
class TargetParams:
    min_pchembl: float = 5.0
    human_only: bool = True
    min_assay_confidence: int = 7
    # ChEMBL assay confidence score: 9=direct single protein, 8=direct protein,
    # 7=functional assay, ≤6=indirect/cell-based/organism-level assay.
    # Use 7 for standard NP target identification (functional assays and above).
    # Set 0 to disable filter. (ChEMBL documentation, 2024)


@dataclass
class DiseaseTargetParams:
    min_score: float = 0.3


@dataclass
class PpiParams:
    min_confidence: float = 0.4
    community_resolution: float = 1.0
    # Leiden resolution parameter γ. Higher γ = more, smaller communities.
    # Default 1.0 typically gives 3–8 communities for typical PPI network sizes.
    # Range [0.1, 3.0] enforced by backend validation.


@dataclass
class HubGeneParams:
    top_n: int = 20
    use_hub_bottleneck: bool = True
    # Hub+bottleneck composite score: 0.5 × norm_degree + 0.5 × norm_betweenness.
    # Identifies nodes with both high connectivity and high information flow.
    # (Jeong et al., Nature 411:41-42, 2001)
    # Set False to rank by degree centrality only (legacy behaviour).


@dataclass
class EnrichmentParams:
    fdr_threshold: float = 0.05
    sources: list[str] = field(default_factory=lambda: ["GO:BP", "GO:MF", "GO:CC", "KEGG"])
    # Enrichment data sources queried via g:Profiler.
    # GO:BP/MF/CC = Gene Ontology functional annotation; KEGG = curated pathways.
    # KEGG is the canonical pathway source in network-pharmacology studies and supplies
    # the hsa##### pathway IDs reported across the reference literature, so GO+KEGG is
    # sufficient for our pathway-level conclusions and validation gates.
    # Reactome (REAC) and WikiPathways (WP) are intentionally NOT queried for now: they
    # overlap heavily with KEGG (redundant near-duplicate hits) and adding them requires
    # output-schema, CSV-export, and frontend-rendering changes. Deferred as a separate
    # feature rather than a methodology gap. (Raudvere et al. 2019, NAR 47:W191)
    #
    # Multiple-testing correction is fixed to Benjamini-Hochberg FDR (not g:Profiler's
    # native g:SCS) — see integrations/gprofiler.py::run_enrichment for the rationale and
    # citation (Benjamini & Hochberg 1995, J. R. Statist. Soc. B 57:289).


@dataclass
class PipelineConfig:
    adme: AdmeParams = field(default_factory=AdmeParams)
    target: TargetParams = field(default_factory=TargetParams)
    disease_targets: DiseaseTargetParams = field(default_factory=DiseaseTargetParams)
    ppi: PpiParams = field(default_factory=PpiParams)
    hub_genes: HubGeneParams = field(default_factory=HubGeneParams)
    enrichment: EnrichmentParams = field(default_factory=EnrichmentParams)

    @classmethod
    def _extract_adme(cls, d: dict[str, Any]) -> dict[str, Any]:
        """Extract AdmeParams kwargs from either nested {"adme": {...}} or flat top-level dict.

        The setup form sends all params flat (e.g. max_mw at top level); the reset-from /
        approve endpoints send them nested under "adme". Support both formats so that ADME
        overrides from the setup form actually reach the pipeline.
        """
        if "adme" in d and isinstance(d["adme"], dict):
            return d["adme"]
        # Flat format — collect known AdmeParams fields from top level
        _ADME_FIELDS = {
            "max_mw", "max_logp", "max_hbd", "max_hba",
            "max_tpsa", "max_rotatable_bonds",
            "apply_veber", "apply_pains", "np_exception_threshold",
            "apply_adme_to_manual",
        }
        return {k: d[k] for k in _ADME_FIELDS if k in d}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "PipelineConfig":
        if not d:
            return cls()
        return cls(
            adme=AdmeParams(**cls._extract_adme(d)),
            target=TargetParams(**d.get("target", {})),
            disease_targets=DiseaseTargetParams(**d.get("disease_targets", {})),
            ppi=PpiParams(**d.get("ppi", {})),
            hub_genes=HubGeneParams(**d.get("hub_genes", {})),
            enrichment=EnrichmentParams(**d.get("enrichment", {})),
        )


@dataclass
class CompoundRecord:
    compound_id: str
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
    is_pains_positive: bool = False
    num_ro5_violations: int | None = None
    source: str = "plant"
    # "plant" — compound retrieved from KNApSAcK plant database
    # "user_provided" — manually injected by researcher via inject-compounds or user-compounds endpoints


@dataclass
class TargetRecord:
    gene_symbol: str
    uniprot_accession: str | None
    source: str  # 'chembl' | 'stitch' | 'disease'
    pchembl_value: float | None = None
    association_score: float | None = None
    compound_ids: list[str] = field(default_factory=list)
