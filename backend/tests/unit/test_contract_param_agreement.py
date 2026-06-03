# backend/tests/unit/test_contract_param_agreement.py
import dataclasses
from app.contracts import PIPELINE_PARAM_FIELDS
from app.schemas.analysis import AnalysisParameters
from analysis.models import PipelineConfig

_SUBMODELS = {
    name: field.annotation
    for name, field in AnalysisParameters.model_fields.items()
}


def _inner_fields(group: str) -> set[str]:
    # annotation is `SubModel | None`; first arg is the submodel
    import typing
    anno = _SUBMODELS[group]
    submodel = typing.get_args(anno)[0]
    return set(submodel.model_fields)


def test_request_model_matches_contract():
    assert set(AnalysisParameters.model_fields) == set(PIPELINE_PARAM_FIELDS)
    for group, fields in PIPELINE_PARAM_FIELDS.items():
        assert _inner_fields(group) == fields, group


def test_pipeline_consumer_matches_contract():
    # PipelineConfig dataclass groups + their fields must match the contract,
    # so the strict request model and the pipeline consumer never drift apart.
    pc_groups = {f.name for f in dataclasses.fields(PipelineConfig)}
    assert pc_groups == set(PIPELINE_PARAM_FIELDS)
    group_to_type = {f.name: f.type for f in dataclasses.fields(PipelineConfig)}
    for group, fields in PIPELINE_PARAM_FIELDS.items():
        sub = {
            "adme": "AdmeParams", "target": "TargetParams",
            "disease_targets": "DiseaseTargetParams", "ppi": "PpiParams",
            "hub_genes": "HubGeneParams", "enrichment": "EnrichmentParams",
        }[group]
        import analysis.models as m
        assert {f.name for f in dataclasses.fields(getattr(m, sub))} == fields, group
