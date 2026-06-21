"""Translation files must stay in sync.

``strings.json`` is the developer source-of-truth; ``translations/en.json``
mirrors it, and every other language file must carry exactly the same keys so
no string silently falls back to English (or lingers after a flow is renamed).
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
    "source, translation",
    [
        ("strings.json", "translations/en.json"),
        ("translations/en.json", "translations/nl.json"),
        ("strings.sensor.json", "translations/sensor.en.json"),
        ("translations/sensor.en.json", "translations/sensor.nl.json"),
    ],
)
def test_translation_keys_match(source, translation):
    src, trans = _keys(source), _keys(translation)
    assert not (src - trans), (
        f"{translation} is missing keys present in {source}: {sorted(src - trans)}"
    )
    assert not (trans - src), (
        f"{translation} has keys not in {source}: {sorted(trans - src)}"
    )
