from __future__ import annotations

from collections import Counter

import pytest

from harmonica.algorithm import AlgorithmGroup, AlgorithmTrack, generate_playlist
from harmonica.config import Settings
from harmonica.covers import cover_log_factor


def _track(
    track_id: int,
    *,
    groups: dict[int, float | None] | None = None,
    sub_group: str | None = None,
    rating: float = 1.0,
    satiation: float = 1.0,
    rediscovery: float = 1.0,
    is_original: bool = False,
    original_prior: float = 1.0,
    is_rated: bool = True,
    repeat_count: float = 0.0,
) -> AlgorithmTrack:
    return AlgorithmTrack(
        id=track_id,
        song_id=f"s{track_id}",
        title=f"T{track_id}",
        artist=None,
        album=None,
        media_asset_id=track_id,
        file_path=None,
        groups=groups or {},
        sub_group=sub_group,
        rating_multiplier=rating,
        # In the two-level path the unit shares this multiplier; keep them equal so a singleton
        # library is provably identical to the legacy path.
        song_rating_multiplier=rating,
        satiation_multiplier=satiation,
        rediscovery_multiplier=rediscovery,
        is_original_rendition=is_original,
        original_prior_mult=original_prior,
        is_rated=is_rated,
        repeat_count=repeat_count,
    )


def test_log_factor_is_logarithmic_not_linear() -> None:
    # base 4: a song's exposure edge from covers grows only logarithmically.
    assert cover_log_factor(1, 4.0) == pytest.approx(1.0)
    assert cover_log_factor(2, 4.0) == pytest.approx(1.5)
    assert cover_log_factor(4, 4.0) == pytest.approx(2.0)
    assert cover_log_factor(8, 4.0) == pytest.approx(2.5)
    assert cover_log_factor(10, 4.0) == pytest.approx(2.6610, abs=1e-3)
    # 10 covers barely beats 9 (the "not twice as likely" property), and a bad base can't divide
    # by zero.
    assert cover_log_factor(10, 4.0) - cover_log_factor(9, 4.0) < 0.1
    assert cover_log_factor(5, 1.0) == cover_log_factor(5, 1.0)  # no ZeroDivisionError


def _varied_library() -> tuple[list[AlgorithmTrack], dict[int, AlgorithmGroup]]:
    groups = {
        1: AlgorithmGroup(1, "Source A", "source"),
        2: AlgorithmGroup(2, "Artist B", "artist"),
        3: AlgorithmGroup(3, "Source C", "source"),
    }
    tracks = [
        _track(1, groups={1: None, 2: None}, rating=1.6, satiation=0.7),
        _track(2, groups={1: None}, rating=0.8),
        _track(3, groups={2: None}, rating=2.0, rediscovery=1.2),
        _track(4, groups={3: None}, rating=1.0),
        _track(5, groups={1: None, 3: None}, rating=1.3, satiation=0.9),
        _track(6, groups={2: None}, rating=0.6),
        _track(7, groups={3: None}, rating=1.1, rediscovery=1.05),
        _track(8, groups={1: None}, rating=1.4),
        _track(9, groups={2: None, 3: None}, rating=0.9),
        _track(10, groups={1: None}, rating=1.2),
    ]
    return tracks, groups


def test_golden_parity_no_covers_is_byte_identical(tmp_path) -> None:
    """The headline safety net: with no sub_groups, enabling two-level selection must produce the
    exact same seeded queue (ids AND scores) as the legacy single-pool generator."""
    tracks, groups = _varied_library()
    off = Settings(home=tmp_path, cover_two_level_enabled=False, cold_start_enabled=False)
    on = Settings(home=tmp_path, cover_two_level_enabled=True, cold_start_enabled=False)

    legacy = generate_playlist(tracks, groups, 120, off, seed="parity")
    twolevel = generate_playlist(tracks, groups, 120, on, seed="parity")

    assert [item.track.id for item in legacy] == [item.track.id for item in twolevel]
    for a, b in zip(legacy, twolevel, strict=True):
        assert a.score == pytest.approx(b.score)


def test_golden_parity_holds_under_cold_start(tmp_path) -> None:
    tracks, groups = _varied_library()
    for track in tracks[:6]:
        object.__setattr__(track, "is_rated", False)  # unrated → cold-start eligible
    off = Settings(home=tmp_path, cover_two_level_enabled=False)
    on = Settings(home=tmp_path, cover_two_level_enabled=True)

    legacy = generate_playlist(tracks, groups, 40, off, seed="cs", cold_start_active=True)
    twolevel = generate_playlist(tracks, groups, 40, on, seed="cs", cold_start_active=True)

    assert [i.track.id for i in legacy] == [i.track.id for i in twolevel]


def test_cover_set_exposure_is_logarithmic_at_clean_state(tmp_path) -> None:
    """At a clean start (nothing played, no groups → every per-cover context is 1), a song with a
    cover set is selected with probability L(n)/(L(n)+singletons) — logarithmic, NOT linear in n."""
    covers = [_track(100 + i, sub_group="big_set") for i in range(4)]  # L(4) = 2.0
    singletons = [_track(i) for i in range(1, 11)]  # 10 singletons
    tracks = covers + singletons
    config = Settings(home=tmp_path, cover_two_level_enabled=True, cold_start_enabled=False)

    set_hits = 0
    trials = 2500
    for i in range(trials):
        item = generate_playlist(tracks, {}, 1, config, seed=f"seed-{i}")[0]
        if item.track.sub_group == "big_set":
            set_hits += 1
    observed = set_hits / trials

    logarithmic = 2.0 / (2.0 + 10)  # ≈ 0.167
    linear = 4.0 / (4.0 + 10)  # ≈ 0.286 — what a naive "count covers" model would give
    assert observed == pytest.approx(logarithmic, abs=0.035)
    assert observed < linear - 0.05  # decisively sublinear


def test_only_one_rendition_per_slot_and_explanation_surfaces_covers(tmp_path) -> None:
    covers = [_track(100 + i, sub_group="set") for i in range(3)]
    tracks = covers + [_track(1), _track(2)]
    config = Settings(home=tmp_path, cover_two_level_enabled=True, cold_start_enabled=False)
    items = generate_playlist(tracks, {}, 30, config, seed="one")

    assert len(items) == 30
    set_items = [i for i in items if i.track.sub_group == "set"]
    assert set_items, "the cover set should appear"
    for item in set_items:
        assert item.explanation["n_covers"] == 3
        assert item.explanation["cover_log_factor"] == pytest.approx(cover_log_factor(3, 4.0))
        assert "unit_weight" in item.explanation


def test_individual_cover_rating_steers_the_rendition_pick(tmp_path) -> None:
    """The shared song rating drives how often the song plays, but the pick BETWEEN renditions also
    uses each cover's own (hidden) individual rating — a better-rated rendition wins more often."""
    better = _track(1, sub_group="anthem", rating=1.8)
    worse = _track(2, sub_group="anthem", rating=0.6)
    config = Settings(home=tmp_path, cover_two_level_enabled=True, cold_start_enabled=False)

    picks = Counter()
    for i in range(2000):
        item = generate_playlist([better, worse], {}, 1, config, seed=f"r{i}")[0]
        picks[item.track.id] += 1
    assert picks[1] > picks[2]


def test_original_rendition_is_favoured_within_a_set(tmp_path) -> None:
    original = _track(1, sub_group="duo", is_original=True, original_prior=1.1)
    cover = _track(2, sub_group="duo")
    config = Settings(home=tmp_path, cover_two_level_enabled=True, cold_start_enabled=False)

    picks = Counter()
    for i in range(2000):
        item = generate_playlist([original, cover], {}, 1, config, seed=f"o{i}")[0]
        picks[item.track.id] += 1

    # The original carries a small (1.1×) within-set prior, so it should win the rendition pick more
    # often than the equally-rated cover — but it's a nudge, not a takeover.
    assert picks[1] > picks[2]
    assert picks[1] < 2 * picks[2]
