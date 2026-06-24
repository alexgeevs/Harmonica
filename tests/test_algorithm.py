from __future__ import annotations

from collections import Counter

import pytest

from harmonica.algorithm import (
    AlgorithmGroup,
    AlgorithmTrack,
    generate_playlist,
    group_sizes,
    linear_recovery,
    score_track,
)
from harmonica.config import Settings


def settings(tmp_path) -> Settings:
    return Settings(home=tmp_path)


def test_large_group_is_sublinear_and_not_dominant(tmp_path) -> None:
    groups: dict[int, AlgorithmGroup] = {1: AlgorithmGroup(1, "Meridian", "source")}
    tracks: list[AlgorithmTrack] = []
    track_id = 1
    for index in range(25):
        tracks.append(
            AlgorithmTrack(
                id=track_id,
                song_id=f"ham_{index}",
                title=f"Meridian {index}",
                artist=None,
                album="Meridian",
                media_asset_id=None,
                file_path=None,
                groups={1: None},
            )
        )
        track_id += 1
    for index in range(25):
        group_id = index + 2
        groups[group_id] = AlgorithmGroup(group_id, f"Standalone {index}", "other")
        tracks.append(
            AlgorithmTrack(
                id=track_id,
                song_id=f"standalone_{index}",
                title=f"Standalone {index}",
                artist=None,
                album=None,
                media_asset_id=None,
                file_path=None,
                groups={group_id: None},
            )
        )
        track_id += 1

    items = generate_playlist(tracks, groups, 600, settings(tmp_path), seed="large-group")
    counts = Counter(
        1 if 1 in item.track.groups else next(iter(item.track.groups)) for item in items
    )

    meridian_count = counts[1]
    singleton_max = max(count for group_id, count in counts.items() if group_id != 1)
    assert meridian_count > singleton_max
    assert meridian_count < 300


def test_overlapping_groups_do_not_double_count(tmp_path) -> None:
    groups = {
        1: AlgorithmGroup(1, "Meridian", "source"),
        2: AlgorithmGroup(2, "Marlowe Vance", "artist"),
        3: AlgorithmGroup(3, "Standalone", "other"),
    }
    tracks = [
        AlgorithmTrack(1, "a", "A", None, None, None, None, {1: None, 2: None}),
        AlgorithmTrack(2, "b", "B", None, None, None, None, {1: None}),
        AlgorithmTrack(3, "c", "C", None, None, None, None, {2: None}),
        AlgorithmTrack(4, "d", "D", None, None, None, None, {3: None}),
    ]
    sizes = group_sizes(tracks, groups)
    last_played = {track.id: -10**9 for track in tracks}
    scores = [
        score_track(
            track,
            groups,
            sizes,
            settings(tmp_path),
            0,
            last_played,
            {},
            {},
        )[0]
        for track in tracks
    ]

    assert scores[0] == pytest.approx(scores[1])
    assert scores[0] == pytest.approx(scores[2])


def test_linear_recovery_floor_and_horizon() -> None:
    assert linear_recovery(None, 100) == 1.0
    assert linear_recovery(0, 100) == 0.0
    assert linear_recovery(50, 100) == pytest.approx(0.5)
    assert linear_recovery(100, 100) == 1.0
    assert linear_recovery(0, 12, floor=0.05) == pytest.approx(0.05)
