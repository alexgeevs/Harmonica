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

    phase = _settle_phase(track_ids, counts, strengths, len(verdicts), settings)
    set_state = session.get(CoverSetState, sub_group)
    total = len(verdicts)
    if set_state is None:
        session.add(
            CoverSetState(
                sub_group=sub_group,
                comparison_phase=phase,
                total_comparisons=total,
            )
        )
    else:
        set_state.total_comparisons = total
        # Never un-settle automatically (only an explicit "compare again" reopens a set).
        if set_state.comparison_phase != "settled":
            set_state.comparison_phase = phase
        set_state.updated_at = now_utc()

    return strengths


def _settle_phase(
    track_ids: list[int],
    counts: dict[int, int],
    strengths: dict[int, float],
    total: int,
    settings: Settings,
) -> str:
    """A set settles (stops prompting) once a hard verdict ceiling is hit, or every rendition has
    enough comparisons AND the ranking is well-separated (adjacent log-strength gaps all clear)."""
    if total == 0:
        return "stars"
    if total >= settings.cover_comparison_max_total:
        return "settled"
    enough = all(
        counts.get(tid, 0) >= settings.cover_comparison_min_per_cover for tid in track_ids
    )
    if enough and len(track_ids) >= 2:
        ordered = sorted((strengths.get(tid, 0.0) for tid in track_ids), reverse=True)
        gaps = [ordered[i] - ordered[i + 1] for i in range(len(ordered) - 1)]
        if gaps and min(gaps) > settings.cover_comparison_settle_gap:
            return "settled"
    return "bootstrapping"


def next_pair(
    session: Session,
    sub_group: str,
    settings: Settings,
) -> tuple[int, int] | None:
    """Pick the most informative A/B pair for a set, or None if it isn't eligible. Informative =
    closest in current strength (outcome most uncertain) and least evidence so far, so verdicts go
    where they resolve the ranking fastest."""
    state = session.get(CoverSetState, sub_group)
    if state is not None and state.comparison_phase == "settled":
        return None
    renditions = list(
        session.scalars(
            select(CoverRenditionState).where(CoverRenditionState.sub_group == sub_group)
        )
    )
    if not renditions:
        # No cache yet (no verdicts) — fall back to the raw set membership.
        ids = set_track_ids(session, sub_group)
        if len(ids) < settings.cover_comparison_min_covers:
            return None
        return (ids[0], ids[1]) if len(ids) >= 2 else None
    if len(renditions) < settings.cover_comparison_min_covers:
        return None

    best: tuple[float, int, int] | None = None
    for i in range(len(renditions)):
        for j in range(i + 1, len(renditions)):
            a, b = renditions[i], renditions[j]
            closeness = 1.0 / (1.0 + abs(a.bt_strength - b.bt_strength))
            sparsity = 1.0 / (1.0 + a.comparison_count + b.comparison_count)
            info = closeness * sparsity
            if best is None or info > best[0]:
                best = (info, a.track_id, b.track_id)
    return (best[1], best[2]) if best else None


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
