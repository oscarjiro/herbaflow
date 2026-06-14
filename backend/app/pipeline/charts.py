"""Stage-5..8 + C-T-P/PPI static chart renderers (matplotlib, headless Agg).

Pure: each function takes already-built data (stage_results slices or a results_handoff graph)
and returns PNG bytes, or None when the chart is not drawable (conditional-PNG rule).
No DB/async/API.
"""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402


def _png(fig: Any) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def render_venn(stage5: dict[str, Any]) -> bytes | None:  # filled in a later task
    return None
