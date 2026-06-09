"""Shadow stub for the rdkit.Chem package — see rdkit/__init__.pyi for why.

This is a *package* stub (not a single-module stub) so that submodule imports such as
``from rdkit.Chem import Crippen, Lipinski, QED, FilterCatalog`` and
``from rdkit.Chem import Descriptors`` resolve here as ``Any`` instead of making mypy descend
into the rdkit wheel's bundled ``rdkit-stubs/Chem/`` package, whose generated ``.pyi`` files
contain syntax errors (e.g. ``rdMolDescriptors.pyi``) that crash mypy at parse time.

Everything is ``Any``.
"""

from typing import Any

def __getattr__(name: str) -> Any: ...
