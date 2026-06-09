"""Local shadow stub for rdkit.

The rdkit wheel bundles a `rdkit-stubs` package whose generated `.pyi` files contain
syntax errors (e.g. a non-default parameter following a default one) that crash mypy at
parse time. Uninstalling those stubs is not durable (they ship inside the rdkit wheel and
return on every `uv sync`), and `ignore_missing_imports` / `follow_imports` do not stop
mypy from parsing an installed stub package.

This minimal shadow sits on `mypy_path` (searched before site-packages), so mypy resolves
the whole `rdkit` namespace here and treats it as untyped (`Any`) without ever reading the
broken bundled stubs. rdkit has no first-party type coverage we rely on; identity logic is
exercised by tests, not the type checker.
"""

from typing import Any

def __getattr__(name: str) -> Any: ...
