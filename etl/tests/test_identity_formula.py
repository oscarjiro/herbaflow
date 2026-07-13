# etl/tests/test_identity_formula.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.identity import formula_matches, hill_formula


def test_neutral_single_component_unchanged():
    # Regression: plain neutral formulas still normalize and compare as before.
    assert hill_formula("C9H8O4") == "C9H8O4"
    assert hill_formula("O4C9H8") == "C9H8O4"
    assert formula_matches("C9H8O4", "C9H8O4") is True
    assert formula_matches("C9H8O4", "C9H8O5") is False


def test_charged_cation_strips_sign():
    # Anthocyanin/flavylium cations carry a trailing '+'; thiamine too.
    assert hill_formula("C15H11O6+") == "C15H11O6"
    assert hill_formula("C12H17N4OS+") == "C12H17N4OS"
    assert formula_matches("C15H11O6+", "C15H11O6") is True
    assert formula_matches("C15H11O6+", "C15H11O6+") is True


def test_multi_digit_and_negative_charge():
    assert hill_formula("C15H11O6+2") == "C15H11O6"
    assert hill_formula("C6H4O4-2") == "C6H4O4"


def test_salt_desalts_to_largest_organic_component():
    # Chloride salt of an anthocyanin: drop the Cl packaging, compare the organic part.
    assert hill_formula("C21H21O11.Cl") == "C21H21O11"
    assert hill_formula("Cl.C21H21O11") == "C21H21O11"  # order-independent
    assert formula_matches("C21H21O11.Cl", "C21H21O11") is True


def test_hydrate_desalts_to_organic():
    assert hill_formula("C6H12O6.H2O") == "C6H12O6"


def test_malformed_still_rejected():
    assert hill_formula("C6H12O6,") == ""
    assert hill_formula("C6H12O6;X") == ""
    assert hill_formula("") == ""
    assert hill_formula("lowercasejunk") == ""
    assert formula_matches("C6H12O6,", "C6H12O6") is False


def test_empty_never_matches():
    assert formula_matches("", "C9H8O4") is False
    assert formula_matches("C9H8O4", "") is False
