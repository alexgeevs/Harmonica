from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from harmonica.config import Settings
from harmonica.models import PlaybackEvent, Track
from harmonica.ratings import effective_rating


@dataclass
class TrackHistorySignal:
    repeat_distance: int | None = None
    repeat_credit: float = 0.0
    skip_penalty: float = 0.0
    repeat_count: float = 0.0


@dataclass
class HistorySummary:
    track_signals: dict[int, TrackHistorySignal] = field(default_factory=dict)
    group_distances: dict[int, int] = field(default_factory=dict)
    group_repeat_credits: dict[int, float] = field(default_factory=dict)
    sub_group_distances: dict[str, int] = field(default_factory=dict)
    sub_group_repeat_credits: dict[str, float] = field(default_factory=dict)
    cold_start_active: bool = False
    rated_track_ids: set[int] = field(default_factory=set)


def summarize_history(
    session: Session,
    tracks: list[Track],
    settings: Settings,
) -> HistorySummary:
    summary = HistorySummary()
    summary.rated_track_ids = rated_track_ids(tracks)

    if not settings.history_influence_enabled:
        summary.cold_start_active = cold_start_is_active(tracks, summary)
        return summary

    events = list(
        session.scalars(
            select(PlaybackEvent)
            .options(selectinload(PlaybackEvent.track).selectinload(Track.memberships))
            .order_by(PlaybackEvent.created_at)
        )
    )
    total_events = len(events)
    track_by_id = {track.id: track for track in tracks}

    # Skip penalty is a RECENCY-WEIGHTED mean of per-event penalties (completions contribute 0),
    # so an old or accidental early skip fades and later completions pull a song back up — instead
    # of the previous permanent max() that floored a song forever on a single skip.
    halflife = max(settings.skip_penalty_halflife, 1.0)
    decay = 0.5 ** (1.0 / halflife)
    penalty_acc: dict[int, list[float]] = {}

    for index, event in enumerate(events):
        track = track_by_id.get(event.track_id)
        if track is None:
            continue
        distance = max(total_events - index - 1, 0)
        repeat_credit, skip_penalty = playback_event_signal(event)
        signal = summary.track_signals.setdefault(event.track_id, TrackHistorySignal())
        signal.repeat_count += repeat_credit
        # Only completed/skipped events carry a quality signal; weight by recency.
        if event.event_type in ("completed", "skipped"):
            weight = decay**distance
            acc = penalty_acc.setdefault(event.track_id, [0.0, 0.0])
            acc[0] += weight * skip_penalty
            acc[1] += weight
        if repeat_credit > 0:
            effective_distance = effective_repeat_distance(distance, repeat_credit)
            if signal.repeat_distance is None or effective_distance < signal.repeat_distance:
                signal.repeat_distance = effective_distance
                signal.repeat_credit = repeat_credit
            for membership in track.memberships:
                update_distance_credit(
                    summary.group_distances,
                    summary.group_repeat_credits,
                    membership.group_id,
                    effective_distance,
                    repeat_credit,
                )
            if track.sub_group:
                update_distance_credit(
                    summary.sub_group_distances,
                    summary.sub_group_repeat_credits,
                    track.sub_group,
                    effective_distance,
                    repeat_credit,
                )

    for track_id, (penalty_sum, weight_total) in penalty_acc.items():
        if weight_total > 0:
            summary.track_signals[track_id].skip_penalty = penalty_sum / weight_total

    summary.cold_start_active = cold_start_is_active(tracks, summary)
    return summary


def playback_event_signal(event: PlaybackEvent) -> tuple[float, float]:
    """(repeat_credit, skip_penalty) for one event, on smooth continuous curves of how much was
    listened — so skip POSITION matters (a 95%-listened skip is near a completion, a 5% skip is a
    strong dislike) instead of the old 3-bin step that collapsed wide ranges together."""
    if event.event_type == "completed":
        return 1.0, 0.0
    if event.event_type != "skipped":
        return 0.0, 0.0

    fraction = listened_fraction(event)
    if fraction is None:
        return 0.5, 0.25
    # repeat_credit ramps 0 (≤10% in) → 1 (≥90% in, treated as a near-completion).
    repeat_credit = min(max((fraction - 0.10) / 0.80, 0.0), 1.0)
    # penalty ramps 1 (≤10% in, a clear early bail) → 0 (≥50% in, you gave it a fair hearing).
    penalty = min(max((0.50 - fraction) / 0.40, 0.0), 1.0)
    return repeat_credit, penalty


def listened_fraction(event: PlaybackEvent) -> float | None:
    if event.duration_seconds is None or event.duration_seconds <= 0:
        return None
    progress = max(event.progress_seconds or 0.0, 0.0)
    return min(progress / event.duration_seconds, 1.0)


def effective_repeat_distance(distance: int, repeat_credit: float) -> int:
    bounded_credit = min(max(repeat_credit, 0.01), 1.0)
    return max(0, round(distance / bounded_credit))


def update_distance_credit(
    distances: dict,
    credits: dict,
    key,
    distance: int,
    credit: float,
) -> None:
    if key not in distances or distance < distances[key]:
        distances[key] = distance
        credits[key] = credit


def rated_track_ids(tracks: list[Track]) -> set[int]:
    rated: set[int] = set()
    for track in tracks:
        if any(rating.value is not None for rating in track.ratings):
            rated.add(track.id)
    return rated


def cold_start_is_active(tracks: list[Track], summary: HistorySummary) -> bool:
    if not tracks:
        return False
    tracks_played_twice = sum(
        1 for signal in summary.track_signals.values() if signal.repeat_count >= 2.0
    )
    return tracks_played_twice <= (len(tracks) / 2)


def history_multiplier(signal: TrackHistorySignal | None, settings: Settings) -> float:
    if signal is None:
        return 1.0
    penalty = min(max(signal.skip_penalty, 0.0), 1.0)
    return max(0.2, 1.0 - (settings.skip_penalty_strength * penalty))


def cold_start_multiplier(
    track: Track,
    summary: HistorySummary,
    settings: Settings,
    variant_count: int,
) -> float:
    if not settings.cold_start_enabled or not summary.cold_start_active:
        return 1.0
    if track.id in summary.rated_track_ids:
        return 1.0
    if effective_rating(track, track.ratings, variant_count) is not None:
        return 1.0
    return settings.cold_start_unrated_boost

