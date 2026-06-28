from __future__ import annotations

from fastapi.testclient import TestClient

from harmonica.api import create_app
from harmonica.config import Settings
from harmonica.schemas import SettingsRead
from harmonica.settings_store import SETTING_DEFINITIONS


def test_every_setting_definition_has_config_and_schema_field() -> None:
    # A user-facing control needs a Settings attribute (so settings_payload can read it) AND a
    # SettingsRead field (or GET /settings validation drops it). Guards against drift.
    settings = Settings()
    read_fields = set(SettingsRead.model_fields)
    for definition in SETTING_DEFINITIONS:
        assert hasattr(settings, definition.key), f"Settings missing '{definition.key}'"
        assert definition.key in read_fields, f"SettingsRead missing '{definition.key}'"


def test_get_settings_exposes_normalisation_controls() -> None:
    with TestClient(create_app()) as client:
        payload = client.get("/settings").json()
        control_keys = {control["key"] for control in payload["controls"]}
        for key in [
            "rating_normalization_enabled",
            "rating_outlier_sd",
            "rating_session_mood_correction",
            "rating_session_min_songs",
            "rating_coverage_ready_fraction",
        ]:
            assert key in control_keys
            assert key in payload  # scalar present at top level too
