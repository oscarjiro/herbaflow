import importlib.util
import sys
from pathlib import Path

ETL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL))

spec = importlib.util.spec_from_file_location(
    "plants_build_part2", ETL / "plants" / "04_build_canonical" / "run_part2.py"
)
mod = importlib.util.module_from_spec(spec)
# Register in sys.modules before exec so @dataclass can resolve __module__
sys.modules["plants_build_part2"] = mod
spec.loader.exec_module(mod)

from shared.identity import plant_alias_id, slugify


def test_alias_key_is_underscore_slug():
    assert mod.build_alias_key("Andrographis paniculata") == "andrographis_paniculata"
    assert mod.build_alias_key("Curcuma longa L.") == slugify("Curcuma longa L.")


def test_alias_id_matches_shared_builder():
    plant_id = "00000000-0000-5000-8000-000000000000"
    key = mod.build_alias_key("Andrographis paniculata")
    assert mod.make_alias_id(plant_id, key) == plant_alias_id(plant_id, key)
