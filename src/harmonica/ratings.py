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


def rating_to_group_multiplier(
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
        return settings.group_rating_min_multiplier + (
            (1.0 - settings.group_rating_min_multiplier) * (bounded / span)
        )
    upper_span = maximum - neutral or 1.0
    return 1.0 + (
        (settings.group_rating_max_multiplier - 1.0) * ((bounded - neutral) / upper_span)
    )


def factor_applies(track: Track, factor: RatingFactor, variant_count: int) -> bool:
    if factor.enabled is False:
        return False
    if track.has_lyrics and factor.applies_to_lyrics is False:
        return False
    if not track.has_lyrics and factor.applies_to_instrumental is False:
        return False
    if factor.applies_to_variants_only is True and variant_count <= 1:
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
        weight = max(rating.factor.weight if rating.factor.weight is not None else 1.0, 0.0)
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


def aggregate_group_rating_multipliers(
    tracks: Iterable[Track],
    variant_counts: dict[str | None, int],
    settings: Settings,
) -> dict[int, float]:
    rating_totals: dict[int, float] = {}
    rating_weights: dict[int, float] = {}
    for track in tracks:
        track_rating = effective_rating(
            track,
            track.ratings,
            variant_counts.get(track.sub_group, 1) if track.sub_group else 1,
        )
        if track_rating is None:
            continue
        memberships = list(track.memberships)
        if not memberships:
            continue
        explicit_total = sum(
            max(membership.share or 0.0, 0.0)
            for membership in memberships
            if membership.share is not None
        )
        for membership in memberships:
            if explicit_total > 0 and membership.share is not None:
                share = max(membership.share, 0.0) / explicit_total
            else:
                share = 1.0 / len(memberships)
            rating_totals[membership.group_id] = rating_totals.get(membership.group_id, 0.0) + (
                track_rating * share
            )
            rating_weights[membership.group_id] = (
                rating_weights.get(membership.group_id, 0.0) + share
            )
    return {
        group_id: rating_to_group_multiplier(total / rating_weights[group_id], settings)
        for group_id, total in rating_totals.items()
        if rating_weights.get(group_id, 0.0) > 0
    }
