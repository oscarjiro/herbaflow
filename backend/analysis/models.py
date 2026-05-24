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
    num_ro5_violations: int | None


@dataclass
class TargetRecord:
    gene_symbol: str
    uniprot_accession: str | None
    source: str  # 'chembl' | 'stitch' | 'disease'
    pchembl_value: float | None = None
    association_score: float | None = None
    compound_ids: list[str] = field(default_factory=list)
