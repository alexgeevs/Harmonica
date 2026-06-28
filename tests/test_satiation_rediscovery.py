from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from harmonica.config import Settings
from harmonica.history import (
    TrackHistorySignal,
    rediscovery_multiplier,
    satiation_multiplier,
)

NOW = datetime(2026, 6, 27, tzinfo=UTC)


def test_satiation_suppresses_a_recent_binge() -> None:
    settings = Settings()
    binged = TrackHistorySignal(recent_play_weight=10.0)
    fresh = TrackHistorySignal(recent_play_weight=0.0)
    assert satiation_multiplier(binged, settings) < 1.0  # over-played recently → eased off
    assert satiation_multiplier(fresh, settings) == 1.0  # not played recently → neutral
    assert satiation_multiplier(binged, settings) >= settings.satiation_floor  # never banned


def test_satiation_disabled_is_neutral() -> None:
    settings = Settings(satiation_enabled=False)
    assert satiation_multiplier(TrackHistorySignal(recent_play_weight=10.0), settings) == 1.0


def test_rediscovery_boosts_a_dormant_favourite_only() -> None:
    settings = Settings()
    dormant = TrackHistorySignal(last_played_at=NOW - timedelta(days=180))
    recent = TrackHistorySignal(last_played_at=NOW - timedelta(days=1))
    # Favourite (overall 4.5 vs library mean 3.0), unheard for months → boosted.
    assert rediscovery_multiplier(dormant, 4.5, 3.0, NOW, settings) > 1.0
    # Same favourite played yesterday → essentially neutral (collapses when recently played).
    assert rediscovery_multiplier(recent, 4.5, 3.0, NOW, settings) == pytest.approx(1.0, abs=0.05)
    # Below the library mean → not a favourite → never resurfaced.
    assert rediscovery_multiplier(dormant, 2.0, 3.0, NOW, settings) == 1.0
    # Never played → cold-start owns it, not rediscovery.
    assert rediscovery_multiplier(TrackHistorySignal(), 4.5, 3.0, NOW, settings) == 1.0


def test_rediscovery_disabled_is_neutral() -> None:
    settings = Settings(rediscovery_enabled=False)
    dormant = TrackHistorySignal(last_played_at=NOW - timedelta(days=180))
    assert rediscovery_multiplier(dormant, 5.0, 3.0, NOW, settings) == 1.0
