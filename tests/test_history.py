from __future__ import annotations

from fastapi.testclient import TestClient

from harmonica.api import create_app
from harmonica.config import Settings
from harmonica.db import SessionLocal
from harmonica.history import playback_event_signal, summarize_history
from harmonica.models import PlaybackEvent, Track


def _signal(progress: float, duration: float = 100.0) -> tuple[float, float]:
    return playback_event_signal(
        PlaybackEvent(
            event_type="skipped", track_id=1, progress_seconds=progress, duration_seconds=duration
        )
    )


def test_early_skip_is_strong_dislike_no_repeat_credit() -> None:
    repeat_credit, skip_penalty = _signal(5)  # 5% listened
    assert repeat_credit == 0.0
    assert skip_penalty == 1.0


def test_skip_signal_is_smooth_and_position_sensitive() -> None:
    # The old 3-bin map scored a 55% and a 95% skip identically; the smooth curve must not.
    credit_55, penalty_55 = _signal(55)
    credit_95, penalty_95 = _signal(95)
    assert credit_95 > credit_55  # listened more => more repeat credit
    assert penalty_55 == 0.0 and penalty_95 == 0.0  # both past the fair-hearing point
    # Mid-skip sits between the extremes.
    credit_40, penalty_40 = _signal(40)
    assert 0.0 < credit_40 < 1.0
    assert 0.0 < penalty_40 < 1.0


def test_completed_track_counts_as_full_repeat() -> None:
    repeat_credit, skip_penalty = playback_event_signal(
        PlaybackEvent(event_type="completed", track_id=1)
    )
    assert repeat_credit == 1.0
    assert skip_penalty == 0.0


def _penalty_after(events: list[PlaybackEvent], song_id: str) -> float:
    with TestClient(create_app()):
        with SessionLocal() as session:
            track = Track(song_id=song_id, title="Recover")
            session.add(track)
            session.commit()
            track_id = track.id
            for event in events:
                event.track_id = track_id
                session.add(event)
                session.commit()  # distinct created_at so recency ordering is well-defined
            summary = summarize_history(session, [session.get(Track, track_id)], Settings())
            return summary.track_signals[track_id].skip_penalty


def test_skip_penalty_recovers_after_later_completions() -> None:
    # THE BUG FIX: one early skip then many completions must NOT leave the song penalised forever.
    early_skip = PlaybackEvent(event_type="skipped", progress_seconds=2, duration_seconds=100)
    completions = [PlaybackEvent(event_type="completed") for _ in range(8)]
    recovered = _penalty_after([early_skip, *completions], "hist_recover")
    assert recovered < 0.2  # recent completions dominate the recency-weighted mean


def test_recent_skip_still_penalises() -> None:
    only_skip = PlaybackEvent(event_type="skipped", progress_seconds=2, duration_seconds=100)
    assert _penalty_after([only_skip], "hist_only_skip") == 1.0
