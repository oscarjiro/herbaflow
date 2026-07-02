from dataclasses import fields

from app.services.descriptors import MolDescriptors


def test_no_qed_field():
    assert "qed_score" not in {f.name for f in fields(MolDescriptors)}
