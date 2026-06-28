"""Rating normalisation (Feature 1).

Turns the append-only ``rating_samples`` history into a single trustworthy per-song
rating, stripped of mood noise. Computed lazily each generation (the library-wide SD
shifts on every write, so nothing is cached per track).

Pipeline per (track, factor) series:  plain mean  ->  [once the library is well-rated]
winsorise outliers to the song's own mean ± k·σ_f  ->  empirical-Bayes shrink toward the
factor's library mean  ->  smooth ramp blend.  σ_f is the POOLED WITHIN-SERIES SD (the
scale of a song's own mood bounce), derived library-wide per the user's direction.

The song-level rating is ``overall`` = 0.5·direct + 0.5·mean(other shared factors), counted
exactly once (no double-count). ``performance`` is cover-specific and never enters here.
Session-mood correction is layered on in Phase B. See the blueprint in
docs/planning/rating-normalization-and-covers.md.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from harmonica.config import Settings
from harmonica.models import RatingFactor, RatingSample, Track
from harmonica.ratings import factor_applies, rating_to_group_multiplier, rating_to_song_multiplier

PERFORMANCE_KEY = "performance"  # cover-specific; excluded from the shared song rating
OVERALL_KEY = "overall"
RAMP_WIDTH = 0.2  # coverage band over which normalisation fades in past the ready threshold


@dataclass(frozen=True)
class FactorStats:
    factor_id: int
    key: str
    mu: float  # library grand mean of the factor
    sigma: float  # pooled within-series SD (a song's own mood-bounce scale)
    coverage: float
    n_samples: int
    n_multi_rated_songs: int
    ready: bool
    alpha: float  # 0..1 ramp weight applied to the normalised estimate


def _clip(value: float, low: float = 0.0, high: float = 5.0) -> float:
    return min(max(value, low), high)


def series_values(values_in_order: Sequence[float | None]) -> list[float]:
    """The live values of one (track, factor) series: everything after the most recent
    retract marker (a NULL). A trailing retract / no values => empty (unrated)."""
    out: list[float] = []
    for value in values_in_order:
        if value is None:
            out = []
        else:
            out.append(float(value))
    return out


def pooled_within_series_sd(series_list: Iterable[list[float]]) -> float:
    """sqrt( Σ_series Σ_i (x_i - mean_series)² / Σ_series (n_series - 1) ) over series with
    n ≥ 2. Measures within-song rating variation (mood), not between-song quality."""
    numerator = 0.0
    denominator = 0
    for values in series_list:
        n = len(values)
        if n < 2:
            continue
        mean = sum(values) / n
        numerator += sum((x - mean) ** 2 for x in values)
        denominator += n - 1
    if denominator <= 0:
        return 0.0
    return math.sqrt(numerator / denominator)


def compute_factor_stats(
    factor: RatingFactor,
    series_by_track: dict[int, list[float]],
    rateable_count: int,
    settings: Settings,
) -> FactorStats:
    all_values = [v for values in series_by_track.values() for v in values]
    n_samples = len(all_values)
    mu = sum(all_values) / n_samples if n_samples else 2.5
    sigma = pooled_within_series_sd(series_by_track.values())
    n_multi = sum(1 for values in series_by_track.values() if len(values) >= 2)
    covered = sum(1 for values in series_by_track.values() if len(values) >= 1)
    coverage = covered / rateable_count if rateable_count > 0 else 0.0
    threshold = settings.rating_coverage_ready_fraction
    ready = (
        settings.rating_normalization_enabled
        and coverage >= threshold
        and n_multi >= settings.rating_min_multi_rated_songs
        and n_samples >= settings.rating_min_samples_for_sd
        and sigma > 1e-6
    )
    alpha = min(1.0, max(0.0, (coverage - threshold) / RAMP_WIDTH)) if ready else 0.0
    return FactorStats(
        factor_id=factor.id,
        key=factor.key,
        mu=mu,
        sigma=sigma,
        coverage=coverage,
        n_samples=n_samples,
        n_multi_rated_songs=n_multi,
        ready=ready,
        alpha=alpha,
    )


def series_effective(values: list[float], stats: FactorStats, settings: Settings) -> float | None:
    """The normalised effective value of one (track, factor) series, or None if unrated."""
    if not values:
        return None
    plain = sum(values) / len(values)
    if not stats.ready:
        return _clip(plain)
    n = len(values)
    if n == 1:
        winsorised = values[0]
    else:
        mean = sum(values) / n
        bound = settings.rating_outlier_sd * stats.sigma
        winsorised = sum(_clip(x, mean - bound, mean + bound) for x in values) / n
    # Empirical-Bayes shrink toward the factor's library mean: a lone rating is pulled
    # halfway to the norm (B=0.5 at n=1, pseudocount 1), a well-rated song is trusted.
    shrink = n / (n + settings.rating_shrinkage_pseudocount)
    normalised = stats.mu + shrink * (winsorised - stats.mu)
    blended = (1.0 - stats.alpha) * plain + stats.alpha * normalised
    return _clip(blended)


def song_overall(
    effective_by_key: dict[str, float | None], applicable_keys: set[str]
) -> float | None:
    """overall = 0.5·direct + 0.5·mean(other shared factors), each counted exactly once.
    Falls back to whichever half is present; None if the song has no usable rating."""
    others = [
        effective_by_key[key]
        for key in applicable_keys
        if key not in (OVERALL_KEY, PERFORMANCE_KEY) and effective_by_key.get(key) is not None
    ]
    direct = effective_by_key.get(OVERALL_KEY)
    others_mean = sum(others) / len(others) if others else None
    if direct is not None and others_mean is not None:
        return 0.5 * direct + 0.5 * others_mean
    if direct is not None:
        return direct
    return others_mean


@dataclass
class SongRatings:
    """Per-track normalised ratings for one generation."""

    overall_by_track: dict[int, float | None]
    effective_by_track: dict[int, dict[str, float | None]]
    factor_stats: dict[int, FactorStats]


def _variant_count(track: Track, variant_counts: dict[str | None, int]) -> int:
    return variant_counts.get(track.sub_group, 1) if track.sub_group else 1


def compute_song_ratings(
    session: Session,
    all_tracks: list[Track],
    variant_counts: dict[str | None, int],
    settings: Settings,
) -> SongRatings:
    """Library-wide factor stats + per-track normalised effective values and ``overall``.

    Stats (mean/SD/coverage/readiness) are whole-library; effective values are computed for
    every track so device-scoped callers can simply look theirs up."""
    factors = list(session.scalars(select(RatingFactor)))
    rated_factors = [f for f in factors if f.key != PERFORMANCE_KEY]

    # Build each (factor, track) series chronologically; a NULL resets the series.
    rows = session.execute(
        select(RatingSample.factor_id, RatingSample.track_id, RatingSample.value).order_by(
            RatingSample.track_id,
            RatingSample.factor_id,
            RatingSample.created_at,
            RatingSample.id,
        )
    ).all()
    series_by_factor: dict[int, dict[int, list[float]]] = {}
    for factor_id, track_id, value in rows:
        track_series = series_by_factor.setdefault(factor_id, {}).setdefault(track_id, [])
        if value is None:
            track_series.clear()
        else:
            track_series.append(float(value))

    stats_by_factor: dict[int, FactorStats] = {}
    for factor in rated_factors:
        rateable = sum(
            1
            for track in all_tracks
            if factor_applies(track, factor, _variant_count(track, variant_counts))
        )
        stats_by_factor[factor.id] = compute_factor_stats(
            factor, series_by_factor.get(factor.id, {}), rateable, settings
        )

    overall_by_track: dict[int, float | None] = {}
    effective_by_track: dict[int, dict[str, float | None]] = {}
    for track in all_tracks:
        effective_by_key: dict[str, float | None] = {}
        applicable: set[str] = set()
        for factor in rated_factors:
            if not factor_applies(track, factor, _variant_count(track, variant_counts)):
                continue
            applicable.add(factor.key)
            values = series_by_factor.get(factor.id, {}).get(track.id, [])
            effective_by_key[factor.key] = series_effective(
                values, stats_by_factor[factor.id], settings
            )
        overall_by_track[track.id] = song_overall(effective_by_key, applicable)
        effective_by_track[track.id] = effective_by_key

    return SongRatings(overall_by_track, effective_by_track, stats_by_factor)


def song_rating_multiplier(track_id: int, ratings: SongRatings, settings: Settings) -> float:
    return rating_to_song_multiplier(ratings.overall_by_track.get(track_id), settings)


def aggregate_group_multipliers_from_overall(
    tracks: list[Track],
    overall_by_track: dict[int, float | None],
    settings: Settings,
) -> dict[int, float]:
    """Group rating multipliers from the SAME normalised per-song overall used for the song
    multiplier — so song and group ratings agree (today they diverge) and a cover set
    contributes once, not once per cover."""
    totals: dict[int, float] = {}
    weights: dict[int, float] = {}
    for track in tracks:
        rating = overall_by_track.get(track.id)
        if rating is None:
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
            totals[membership.group_id] = totals.get(membership.group_id, 0.0) + rating * share
            weights[membership.group_id] = weights.get(membership.group_id, 0.0) + share
    return {
        group_id: rating_to_group_multiplier(totals[group_id] / weights[group_id], settings)
        for group_id in totals
        if weights.get(group_id, 0.0) > 0
    }
