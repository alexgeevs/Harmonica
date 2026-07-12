"""Demo driver. Runs Harmonica's real algorithm files in the browser through Pyodide.

``algorithm.py``, ``history.py`` and ``ratings.py`` are the exact files from ``src/harmonica``,
copied in at deploy time (see site/demo/README.md). This driver stubs the imports they expect
(``sqlalchemy``, ``harmonica.config``, ``harmonica.models``) so they load unchanged, rebuilds the
inputs that ``src/harmonica/playlist.py`` would normally read from the database out of the JSON
the page sends, and returns a generated queue as JSON.

Deliberate demo simplifications, each mirroring a documented settings path in the full app:
- rating normalisation is off (one user, one session, few ratings), so the plain rating path
  from ``ratings.py`` is used, exactly as ``rating_normalization_enabled=False`` would at home
- rediscovery is fed the plain overall rating and library mean instead of the normalised ones
- every track is a YouTube video, so the visual-priority multiplier is left off (it would be
  uniform across the whole pool and change nothing)
- there are no version families in the demo, so the two-level cover path stays off (its default)
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Stub the modules the real files import, so they run verbatim without a
# database. Registered in sys.modules BEFORE the real files are imported.
# ---------------------------------------------------------------------------


class _Chain:
    """Stands in for sqlalchemy query builders. Every call and attribute returns itself. The
    fake session below ignores the query object entirely and returns the event list."""

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return self


_sqlalchemy = types.ModuleType("sqlalchemy")
_sqlalchemy.select = _Chain()
_sqlalchemy.func = _Chain()
_sqlalchemy_orm = types.ModuleType("sqlalchemy.orm")
_sqlalchemy_orm.Session = object
_sqlalchemy_orm.selectinload = _Chain()
_sqlalchemy.orm = _sqlalchemy_orm
sys.modules["sqlalchemy"] = _sqlalchemy
sys.modules["sqlalchemy.orm"] = _sqlalchemy_orm


@dataclass
class Settings:
    """The algorithm-relevant fields of harmonica.config.Settings with the same defaults."""

    beta: float = 1.25
    group_cooldown_floor: float = 0.05
    sub_group_cooldown_floor: float = 0.01
    song_rating_min_multiplier: float = 0.5
    song_rating_max_multiplier: float = 2.0
    group_rating_min_multiplier: float = 0.7
    group_rating_max_multiplier: float = 1.4
    enable_group_rating_multiplier: bool = True
    history_influence_enabled: bool = True
    skip_penalty_strength: float = 0.25
    skip_penalty_halflife: float = 30.0
    cold_start_enabled: bool = True
    cold_start_unrated_boost: float = 2.0
    visual_priority_enabled: bool = False
    visual_priority_multiplier: float = 1.35
    group_clustering_bias: float = 0.0
    tag_clustering_bias: float = 0.0
    satiation_enabled: bool = True
    satiation_strength: float = 0.5
    satiation_window_days: float = 14.0
    satiation_floor: float = 0.3
    rediscovery_enabled: bool = True
    rediscovery_strength: float = 0.4
    rediscovery_halflife_days: float = 60.0
    favourite_pacing_enabled: bool = False
    favourite_pacing_strength: float = 1.5
    avoid_consecutive_compressed: bool = True
    cover_two_level_enabled: bool = False


_config = types.ModuleType("harmonica.config")
_config.Settings = Settings


def _now_utc() -> datetime:
    return datetime.now(UTC)


# The model names are only ever used inside query builders (PlaybackEvent.track and so on) or as
# type annotations, which stay strings under future-annotations. _Chain swallows both shapes.
_models = types.ModuleType("harmonica.models")
_models.PlaybackEvent = _Chain()
_models.Track = _Chain()
_models.TrackRating = _Chain()
_models.RatingFactor = _Chain()
_models.now_utc = _now_utc

_package = types.ModuleType("harmonica")
_package.__path__ = ["/harmonica_src"]

sys.modules["harmonica"] = _package
sys.modules["harmonica.config"] = _config
sys.modules["harmonica.models"] = _models

# ---------------------------------------------------------------------------
# The real thing. These import the unmodified files the page wrote to
# /harmonica_src, resolving their harmonica.* imports to the stubs above.
# ---------------------------------------------------------------------------

import json  # noqa: E402

from harmonica.algorithm import AlgorithmGroup, AlgorithmTrack, generate_playlist  # noqa: E402
from harmonica.history import (  # noqa: E402
    cold_start_multiplier,
    history_multiplier,
    rediscovery_multiplier,
    satiation_multiplier,
    summarize_history,
)
from harmonica.ratings import (  # noqa: E402
    aggregate_group_rating_multipliers,
    effective_rating,
    effective_song_multiplier,
)


class _FakeSession:
    """summarize_history's only database touch is session.scalars(query) for the ordered event
    list. Hand it the events directly and the rest of the function runs as written."""

    def __init__(self, events: list) -> None:
        self._events = events

    def scalars(self, _query):
        return list(self._events)


@dataclass
class _Factor:
    key: str = "overall"
    weight: float = 1.0
    enabled: bool = True
    applies_to_lyrics: bool = True
    applies_to_instrumental: bool = True
    applies_to_variants_only: bool = False


_OVERALL = _Factor()


@dataclass
class _Rating:
    value: float | None
    factor: _Factor = field(default_factory=lambda: _OVERALL)


@dataclass
class _Membership:
    group_id: int
    share: float | None = None


@dataclass
class _FakeTrack:
    id: int
    memberships: list
    ratings: list
    sub_group: str | None = None
    has_lyrics: bool = False


@dataclass
class _FakeEvent:
    track_id: int
    event_type: str
    created_at: datetime
    duration_seconds: float | None
    progress_seconds: float | None


def _parse_when(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def generate_queue(payload_json: str) -> str:
    """payload: tracks [{id, videoId, title, artist, uploader, groupId, rating}], groups
    [{id, name}], events [{trackId, eventType, createdAt, durationSeconds, progressSeconds}],
    length, seed, and optional settings overrides. Returns the generated items as JSON."""
    payload = json.loads(payload_json)
    settings = Settings()
    for key, value in (payload.get("settings") or {}).items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    rows = payload.get("tracks") or []
    if not rows:
        return json.dumps([])
    length = max(1, min(int(payload.get("length") or 12), 100))
    seed = payload.get("seed")
    now = _now_utc()

    fake_tracks = [
        _FakeTrack(
            id=row["id"],
            memberships=[_Membership(group_id=row["groupId"])],
            ratings=[_Rating(value=row.get("rating"))],
        )
        for row in rows
    ]
    fake_by_id = {track.id: track for track in fake_tracks}

    events = sorted(
        (
            _FakeEvent(
                track_id=event["trackId"],
                event_type=event["eventType"],
                created_at=_parse_when(event["createdAt"]),
                duration_seconds=event.get("durationSeconds"),
                progress_seconds=event.get("progressSeconds"),
            )
            for event in (payload.get("events") or [])
        ),
        key=lambda event: event.created_at,
    )

    # The same assembly src/harmonica/playlist.py does, over the page's data instead of the DB.
    summary = summarize_history(_FakeSession(events), fake_tracks, settings, now=now)

    group_multipliers = (
        aggregate_group_rating_multipliers(fake_tracks, {}, settings)
        if settings.enable_group_rating_multiplier
        else {}
    )
    groups = {
        group["id"]: AlgorithmGroup(
            id=group["id"],
            name=group["name"],
            group_type="uploader",
            multiplier=group_multipliers.get(group["id"], 1.0),
        )
        for group in (payload.get("groups") or [])
    }

    overall_by_track = {
        track.id: effective_rating(track, track.ratings, 1) for track in fake_tracks
    }
    rated = [value for value in overall_by_track.values() if value is not None]
    library_mean = sum(rated) / len(rated) if rated else None

    algorithm_tracks = []
    for row in rows:
        fake = fake_by_id[row["id"]]
        signal = summary.track_signals.get(row["id"])
        algorithm_tracks.append(
            AlgorithmTrack(
                id=row["id"],
                song_id=row["videoId"],
                title=row["title"],
                artist=row.get("artist"),
                album=None,
                media_asset_id=None,
                file_path=None,
                groups={row["groupId"]: None},
                sub_group=None,
                manual_multiplier=1.0,
                rating_multiplier=effective_song_multiplier(fake, fake.ratings, 1, settings),
                history_multiplier=history_multiplier(signal, settings),
                cold_start_multiplier=cold_start_multiplier(fake, summary, settings, 1),
                satiation_multiplier=satiation_multiplier(signal, settings),
                rediscovery_multiplier=rediscovery_multiplier(
                    signal, overall_by_track.get(row["id"]), library_mean, now, settings
                ),
                has_video=True,
                repeat_count=signal.repeat_count if signal else 0.0,
                is_rated=row["id"] in summary.rated_track_ids,
                is_compressed=False,
            )
        )

    track_distances = {
        track_id: signal.repeat_distance
        for track_id, signal in summary.track_signals.items()
        if signal.repeat_distance is not None
    }
    track_credits = {
        track_id: signal.repeat_credit
        for track_id, signal in summary.track_signals.items()
        if signal.repeat_distance is not None
    }
    track_counts = {
        track_id: signal.repeat_count for track_id, signal in summary.track_signals.items()
    }

    items = generate_playlist(
        algorithm_tracks,
        groups,
        length,
        settings,
        seed=seed,
        ui_active=False,
        initial_track_distances=track_distances,
        initial_group_distances=summary.group_distances,
        initial_sub_group_distances=summary.sub_group_distances,
        initial_track_repeat_credits=track_credits,
        initial_group_repeat_credits=summary.group_repeat_credits,
        initial_sub_group_repeat_credits=summary.sub_group_repeat_credits,
        initial_track_repeat_counts=track_counts,
        cold_start_active=summary.cold_start_active,
    )

    by_id = {row["id"]: row for row in rows}
    return json.dumps(
        [
            {
                "position": item.position,
                "trackId": item.track.id,
                "videoId": item.track.song_id,
                "title": item.track.title,
                "artist": item.track.artist,
                "uploader": by_id[item.track.id].get("uploader"),
                "score": item.score,
                "explanation": {
                    key: value
                    for key, value in item.explanation.items()
                    if key != "top_candidates"
                },
            }
            for item in items
        ]
    )
