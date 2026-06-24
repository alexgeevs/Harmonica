from __future__ import annotations

import pytest

from harmonica.config import Settings
from harmonica.models import GroupMembership, RatingFactor, Track, TrackRating
from harmonica.ratings import (
    aggregate_group_rating_multipliers,
    effective_rating,
    rating_to_song_multiplier,
)


def test_rating_multiplier_maps_zero_neutral_and_five(tmp_path) -> None:
    config = Settings(home=tmp_path)
    assert rating_to_song_multiplier(0, config) == pytest.approx(0.5)
    assert rating_to_song_multiplier(2.5, config) == pytest.approx(1.0)
    assert rating_to_song_multiplier(5, config) == pytest.approx(2.0)


def test_effective_rating_ignores_non_applicable_factors() -> None:
    track = Track(song_id="instrumental", title="Instrumental", has_lyrics=False)
    lyrics = RatingFactor(
        key="lyrics",
        label="Lyrics",
        applies_to_lyrics=True,
        applies_to_instrumental=False,
    )
    focus = RatingFactor(
        key="focus",
        label="Focus",
        applies_to_lyrics=False,
        applies_to_instrumental=True,
    )
    performance = RatingFactor(
        key="performance",
        label="Performance",
        applies_to_variants_only=True,
    )
    ratings = [
        TrackRating(track=track, factor=lyrics, value=5),
        TrackRating(track=track, factor=focus, value=4),
        TrackRating(track=track, factor=performance, value=1),
    ]

    assert effective_rating(track, ratings, variant_count=1) == pytest.approx(4.0)


def test_group_rating_aggregates_from_member_track_ratings(tmp_path) -> None:
    config = Settings(home=tmp_path)
    music = RatingFactor(key="music", label="Music", weight=1.0)
    excellent = Track(song_id="excellent", title="Excellent")
    weak = Track(song_id="weak", title="Weak")
    excellent.memberships = [GroupMembership(group_id=1, share=None)]
    weak.memberships = [GroupMembership(group_id=1, share=None)]
    excellent.ratings = [TrackRating(factor=music, value=5)]
    weak.ratings = [TrackRating(factor=music, value=3)]

    multipliers = aggregate_group_rating_multipliers([excellent, weak], {}, config)

    assert multipliers[1] > 1.0
    assert multipliers[1] <= config.group_rating_max_multiplier
