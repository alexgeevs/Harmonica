"""Recompute Bradley-Terry rendition strengths from the raw verdict log and cache them (Phase D).

The cache (``CoverRenditionState``) is what the generator reads each slot; it is always rebuilt from
the full ``CoverComparison`` history so the ranking is order-independent and self-healing if a
verdict is deleted.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from harmonica.bt import fit_strengths
from harmonica.config import Settings
from harmonica.models import (
    CoverComparison,
    CoverRenditionState,
    CoverSetState,
    Track,
    now_utc,
)


def set_track_ids(session: Session, sub_group: str) -> list[int]:
    """All renditions belonging to a cover set (every track sharing the ``sub_group``)."""
    return list(
        session.scalars(select(Track.id).where(Track.sub_group == sub_group).order_by(Track.id))
    )


def recompute_set(session: Session, sub_group: str, settings: Settings) -> dict[int, float]:
    """Refit Bradley-Terry for one set and refresh its rendition/set caches. Returns the strengths.
    Does not commit — the caller owns the transaction."""
    track_ids = set_track_ids(session, sub_group)
    verdicts = [
        (row.track_a_id, row.track_b_id, row.winner_track_id)
        for row in session.scalars(
            select(CoverComparison).where(CoverComparison.sub_group == sub_group)
        )
    ]
    strengths = fit_strengths(
        track_ids, verdicts, prior_strength=settings.cover_bt_prior_strength
    )

    # Per-rendition comparison counts (how much evidence backs each strength).
    counts: dict[int, int] = dict.fromkeys(track_ids, 0)
    for a, b, _ in verdicts:
        if a in counts:
            counts[a] += 1
        if b in counts:
            counts[b] += 1

    existing = {
        row.track_id: row
        for row in session.scalars(
            select(CoverRenditionState).where(CoverRenditionState.sub_group == sub_group)
        )
    }
    for track_id in track_ids:
        strength = strengths.get(track_id, 0.0)
        row = existing.get(track_id)
        if row is None:
            session.add(
                CoverRenditionState(
                    track_id=track_id,
                    sub_group=sub_group,
                    bt_strength=strength,
                    comparison_count=counts.get(track_id, 0),
                )
            )
        else:
            row.bt_strength = strength
            row.comparison_count = counts.get(track_id, 0)
            row.updated_at = now_utc()

    set_state = session.get(CoverSetState, sub_group)
    total = len(verdicts)
    if set_state is None:
        session.add(
            CoverSetState(
                sub_group=sub_group,
                comparison_phase="bootstrapping" if total else "stars",
                total_comparisons=total,
            )
        )
    else:
        set_state.total_comparisons = total
        if total and set_state.comparison_phase == "stars":
            set_state.comparison_phase = "bootstrapping"
        set_state.updated_at = now_utc()

    return strengths


def record_verdict(
    session: Session,
    sub_group: str,
    track_a_id: int,
    track_b_id: int,
    winner_track_id: int | None,
    settings: Settings,
    pct_a: float | None = None,
    pct_b: float | None = None,
    session_id: str | None = None,
    run_id: int | None = None,
) -> dict[int, float]:
    """Append one A/B verdict and refit the set. Returns the refreshed strengths."""
    session.add(
        CoverComparison(
            sub_group=sub_group,
            track_a_id=track_a_id,
            track_b_id=track_b_id,
            winner_track_id=winner_track_id,
            pct_a=pct_a,
            pct_b=pct_b,
            session_id=session_id,
            run_id=run_id,
        )
    )
    session.flush()
    return recompute_set(session, sub_group, settings)


def rendition_states(session: Session) -> dict[int, CoverRenditionState]:
    """All cached rendition states keyed by track id (for the generator to read in one query)."""
    return {row.track_id: row for row in session.scalars(select(CoverRenditionState))}
