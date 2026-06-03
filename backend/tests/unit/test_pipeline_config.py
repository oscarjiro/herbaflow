from analysis.models import PipelineConfig


def test_nested_overrides_read():
    cfg = PipelineConfig.from_dict({"adme": {"max_mw": 600}, "target": {"min_pchembl": 6.0}})
    assert cfg.adme.max_mw == 600
    assert cfg.target.min_pchembl == 6.0


def test_defaults_when_absent():
    cfg = PipelineConfig.from_dict({})
    assert cfg.adme.max_mw == 500.0
    assert cfg.hub_genes.top_n == 20


def test_ignores_control_keys():
    cfg = PipelineConfig.from_dict({"_plant_ids": ["p"], "_input_mode": "manual_compounds"})
    assert cfg.adme.max_mw == 500.0
