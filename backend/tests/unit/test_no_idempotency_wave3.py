import inspect

from app.repositories.analysis import AnalysisRepository
from app.services.analysis import AnalysisService


def test_idempotency_surface_gone():
    assert "idempotency_key" not in inspect.signature(AnalysisService.create).parameters
    assert "idempotency_key" not in inspect.signature(AnalysisRepository.create).parameters
    assert not hasattr(AnalysisRepository, "get_by_idempotency_key")
