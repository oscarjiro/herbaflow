"""Readable, conventional application logging for the ``herbaflow`` namespace.

One handler on the ``herbaflow`` parent logger emits a clean single-line format to stdout
(`HH:MM:SS LEVEL  herbaflow.area | message`). Every app module logs through a
``logging.getLogger("herbaflow.<area>")`` child, so the whole backend narrates what it does
(validating, enriching, stage math, run transitions) in one consistent, greppable stream.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Attach the single ``herbaflow`` stdout handler. Idempotent (safe to call repeatedly)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logger = logging.getLogger("herbaflow")
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(handler)
    logger.propagate = False  # our own handler; don't double-emit through uvicorn's root
    _CONFIGURED = True
