from __future__ import annotations

from collections.abc import Iterable

from harmonica.config import Settings
from harmonica.models import RatingFactor, Track, TrackRating


def rating_to_song_multiplier(
    rating: float | None,
    settings: Settings,
    neutral: float = 2.5,
    maximum: float = 5.0,
) -> float:
    if rating is None:
        return 1.0
    bounded = min(max(rating, 0.0), maximum)
    if bounded <= neutral:
        span = neutral or 1.0
        return settings.song_rating_min_multiplier + (
            (1.0 - settings.song_rating_min_multiplier) * (bounded / span)
        )
    upper_span = maximum - neutral or 1.0
    return 1.0 + (
        (settings.song_rating_max_multiplier - 1.0) * ((bounded - neutral) / upper_span)
    )


def factor_applies(track: Track, factor: RatingFactor, variant_count: int) -> bool:
    if not factor.enabled:
        return False
    if track.has_lyrics and not factor.applies_to_lyrics:
        return False
    if not track.has_lyrics and not factor.applies_to_instrumental:
        return False
    if factor.applies_to_variants_only and variant_count <= 1:
        return False
    return True


def effective_rating(
    track: Track,
    ratings: Iterable[TrackRating],
    variant_count: int,
) -> float | None:
    weighted_sum = 0.0
    total_weight = 0.0
    for rating in ratings:
        if rating.value is None or rating.factor is None:
            continue
        if not factor_applies(track, rating.factor, variant_count):
            continue
        weight = max(rating.factor.weight, 0.0)
        weighted_sum += min(max(rating.value, 0.0), 5.0) * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    return weighted_sum / total_weight


def effective_song_multiplier(
    track: Track,
    ratings: Iterable[TrackRating],
    variant_count: int,
    settings: Settings,
) -> float:
    return rating_to_song_multiplier(effective_rating(track, ratings, variant_count), settings)

