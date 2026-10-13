import pytest

from siro.adapters.wot import translate_thing_description


def test_r03_limited_wot_translation_and_explicit_rejection() -> None:
    descriptor = translate_thing_description(
        {
            "title": "lamp",
            "properties": {"power": {"type": "boolean"}},
            "actions": {"toggle": {}},
            "events": {"changed": {}},
        }
    )
    assert descriptor.device_id == "wot:lamp"
    assert set(descriptor.properties) == {"power"}
    assert set(descriptor.actions) == {"toggle"}
    with pytest.raises(ValueError, match="security"):
        translate_thing_description({"title": "secure", "security": ["bearer"]})
