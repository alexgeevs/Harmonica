from __future__ import annotations

from harmonica.history import playback_event_signal
from harmonica.models import PlaybackEvent


def test_skip_under_ten_percent_is_bad_but_not_recent_play() -> None:
    event = PlaybackEvent(
        event_type="skipped",
        track_id=1,
        progress_seconds=5,
        duration_seconds=100,
    )

    repeat_credit, skip_penalty = playback_event_signal(event)
    assert repeat_credit == 0.0
    assert skip_penalty == 1.0


def test_skip_under_half_is_partial_repeat_and_bad_signal() -> None:
    event = PlaybackEvent(
        event_type="skipped",
        track_id=1,
        progress_seconds=40,
        duration_seconds=100,
    )

    repeat_credit, skip_penalty = playback_event_signal(event)
    assert repeat_credit == 0.5
    assert skip_penalty == 0.5


def test_completed_track_counts_as_full_repeat() -> None:
    event = PlaybackEvent(event_type="completed", track_id=1)

    repeat_credit, skip_penalty = playback_event_signal(event)
    assert repeat_credit == 1.0
    assert skip_penalty == 0.0
