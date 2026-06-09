"""The herbaflow logging setup is configured once and is greppable."""

from __future__ import annotations

import logging

from app.logging_config import configure_logging


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    parent = logging.getLogger("herbaflow")
    before = len(parent.handlers)
    configure_logging()  # second call must not add another handler
    assert len(parent.handlers) == before
    assert parent.level == logging.INFO
    assert parent.propagate is False
