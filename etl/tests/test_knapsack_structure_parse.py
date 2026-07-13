# etl/tests/test_knapsack_structure_parse.py
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
spec = importlib.util.spec_from_file_location(
    "knapsack_main", Path(__file__).resolve().parents[1] / "knapsack" / "main.py"
)
knapsack_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(knapsack_main)

_PAGE = """
<table class="d3">
  <tr><th class="inf">CAS RN</th><td colspan="4">60491-91-0</td></tr>
  <tr><th class="inf">Formula</th><td colspan="4">C19H24O6</td></tr>
  <tr><th class="inf">InChIKey</th><td colspan="4">IGZIQAJJXGRAJF-OSTHPMNLNA-N</td></tr>
  <tr><th class="inf">InChICode</th><td colspan="4">InChI=1S/C19H24O6/x</td></tr>
  <tr><th class="inf">SMILES</th><td colspan="4">C=C1C[C@]23C[C@H]1CC[C@H]2C(=O)O</td></tr>
</table>
"""


def test_parses_structure_fields():
    got = knapsack_main.parse_structure_page(_PAGE)
    assert got["knapsack_inchikey"] == "IGZIQAJJXGRAJF-OSTHPMNLNA-N"
    assert got["knapsack_smiles"] == "C=C1C[C@]23C[C@H]1CC[C@H]2C(=O)O"
    assert got["knapsack_formula"] == "C19H24O6"


def test_missing_fields_blank_not_error():
    got = knapsack_main.parse_structure_page("<table class='d3'></table>")
    assert got == {"knapsack_inchikey": "", "knapsack_smiles": "", "knapsack_formula": ""}


def test_inchikey_not_confused_with_inchicode():
    # InChICode row must not leak into the InChIKey field.
    got = knapsack_main.parse_structure_page(_PAGE)
    assert "InChI=1S" not in got["knapsack_inchikey"]
