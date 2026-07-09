from __future__ import annotations

from harmonica.algorithm import AlgorithmTrack, score_track
from harmonica.config import Settings


def _track(
    track_id: int, *, favourite: bool, satiation: float, rediscovery: float
) -> AlgorithmTrack:
    # No groups → base_score 1.0, so the score is just the product of the multipliers under test.
    return AlgorithmTrack(
        id=track_id,
        song_id=f"s{track_id}",
        title=f"Song {track_id}",
        artist=None,
        album=None,
        media_asset_id=None,
        file_path=None,
        satiation_multiplier=satiation,
        rediscovery_multiplier=rediscovery,
        favourite=favourite,
    )


def _score(track: AlgorithmTrack, settings: Settings) -> float:
    value, _ = score_track(
        track,
        groups={},
        sizes={},
        settings=settings,
        current_index=0,
        track_last_played={},
        group_last_played={},
        sub_group_last_played={},
    )
    return value


def test_favourite_pacing_amplifies_satiation_and_rediscovery_for_favourites() -> None:
    settings = Settings(favourite_pacing_enabled=True, favourite_pacing_strength=2.0)
    fav = _track(1, favourite=True, satiation=0.5, rediscovery=1.4)
    plain = _track(2, favourite=False, satiation=0.5, rediscovery=1.4)

    # Non-favourite is untouched: score is exactly satiation * rediscovery.
    assert _score(plain, settings) == 0.5 * 1.4
    # Favourite: each multiplier is pushed twice as far from 1.0.
    # satiation 0.5 -> 1 + (0.5-1)*2 = 0.0 ; rediscovery 1.4 -> 1 + (1.4-1)*2 = 1.8
    assert _score(fav, settings) == 0.0 * 1.8


def test_favourite_pacing_is_inert_by_default_and_when_disabled() -> None:
    fav = _track(1, favourite=True, satiation=0.5, rediscovery=1.4)
    baseline = 0.5 * 1.4
    # Default settings: feature off -> favourite scored like any other song.
    assert _score(fav, Settings()) == baseline
    # Explicitly disabled with a strength set: still inert.
    disabled = Settings(favourite_pacing_enabled=False, favourite_pacing_strength=2.0)
    assert _score(fav, disabled) == baseline
