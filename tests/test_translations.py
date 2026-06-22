"""Translation files must stay in sync.

``strings.json`` is the developer source-of-truth and ``translations/en.json``
mirrors it exactly. Localized files (e.g. ``nl.json``) must fully translate the
interactive UI (config/options/services/exceptions) and must not carry stale
keys, but may omit ``entity.*`` names: Home Assistant falls back to English for
those, and hand-maintaining a name for every register in every language is not
required.
"""
import json
from pathlib import Path

import pytest

COMP = Path(__file__).resolve().parents[1] / "custom_components" / "growatt_modbus"


def _flatten(data, prefix=""):
    out = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out.update(_flatten(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


def _keys(rel_path):
    return set(_flatten(json.loads((COMP / rel_path).read_text())))


@pytest.mark.parametrize(
    "source, translation, full_mirror",
    [
        ("strings.json", "translations/en.json", True),
        ("translations/en.json", "translations/nl.json", False),
        ("strings.sensor.json", "translations/sensor.en.json", True),
        ("translations/sensor.en.json", "translations/sensor.nl.json", False),
    ],
)
def test_translation_keys_match(source, translation, full_mirror):
    src, trans = _keys(source), _keys(translation)
    missing = src - trans
    if not full_mirror:
        # Localized files may fall back to English for entity names.
        missing = {key for key in missing if not key.startswith("entity.")}
    assert not missing, (
        f"{translation} is missing keys present in {source}: {sorted(missing)}"
    )
    assert not (trans - src), (
        f"{translation} has keys not in {source}: {sorted(trans - src)}"
    )
