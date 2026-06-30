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
    UserCoverSetState,
    now_utc,
)


def set_track_ids(session: Session, sub_group: str) -> list[int]:
    """All renditions belonging to a cover set (every track sharing the ``sub_group``)."""
    return list(
        session.scalars(select(Track.id).where(Track.sub_group == sub_group).order_by(Track.id))
    )


def _set_verdicts(
    session: Session, sub_group: str, owner_config_id: int | None
) -> list[tuple[int, int, int | None]]:
    """The A/B verdicts for one set, scoped to one owner (or the legacy/unowned NULL rows)."""
    query = select(CoverComparison).where(CoverComparison.sub_group == sub_group)
    if owner_config_id is None:
        query = query.where(CoverComparison.owner_config_id.is_(None))
    else:
        query = query.where(CoverComparison.owner_config_id == owner_config_id)
    return [(row.track_a_id, row.track_b_id, row.winner_track_id) for row in session.scalars(query)]


def _verdict_counts(
    track_ids: list[int], verdicts: list[tuple[int, int, int | None]]
) -> dict[int, int]:
    counts: dict[int, int] = dict.fromkeys(track_ids, 0)
    for a, b, _ in verdicts:
        if a in counts:
            counts[a] += 1
        if b in counts:
            counts[b] += 1
    return counts


def owner_set_state(
    session: Session, sub_group: str, owner_config_id: int
) -> UserCoverSetState | None:
    return session.scalar(
        select(UserCoverSetState).where(
            UserCoverSetState.owner_config_id == owner_config_id,
            UserCoverSetState.sub_group == sub_group,
        )
    )


def recompute_set(
    session: Session,
    sub_group: str,
    settings: Settings,
    owner_config_id: int | None = None,
) -> dict[int, float]:
    """Refit Bradley-Terry for one set from its (owner-scoped) verdict log. The legacy/unowned path
    refreshes the shared ``CoverRenditionState``/``CoverSetState`` caches; an owned profile persists
    only its phase in ``UserCoverSetState`` and recomputes rendition strengths in-memory elsewhere.
    Returns the strengths. Does not commit — the caller owns the transaction."""
    track_ids = set_track_ids(session, sub_group)
    verdicts = _set_verdicts(session, sub_group, owner_config_id)
    strengths = fit_strengths(
        track_ids, verdicts, prior_strength=settings.cover_bt_prior_strength
    )
    counts = _verdict_counts(track_ids, verdicts)
    phase = _settle_phase(track_ids, counts, strengths, len(verdicts), settings)

    if owner_config_id is not None:
        state = owner_set_state(session, sub_group, owner_config_id)
        if state is None:
            session.add(
                UserCoverSetState(
                    owner_config_id=owner_config_id,
                    sub_group=sub_group,
                    comparison_phase=phase,
                    total_comparisons=len(verdicts),
                )
            )
        else:
            state.total_comparisons = len(verdicts)
            if state.comparison_phase != "settled":
                state.comparison_phase = phase
            state.updated_at = now_utc()
        return strengths

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


def _informative_pair(
    strengths: dict[int, float], counts: dict[int, int], track_ids: list[int]
) -> tuple[int, int] | None:
    best: tuple[float, int, int] | None = None
    for i in range(len(track_ids)):
        for j in range(i + 1, len(track_ids)):
            a, b = track_ids[i], track_ids[j]
            closeness = 1.0 / (1.0 + abs(strengths.get(a, 0.0) - strengths.get(b, 0.0)))
            sparsity = 1.0 / (1.0 + counts.get(a, 0) + counts.get(b, 0))
            info = closeness * sparsity
            if best is None or info > best[0]:
                best = (info, a, b)
    return (best[1], best[2]) if best else None


def next_pair(
    session: Session,
    sub_group: str,
    settings: Settings,
    owner_config_id: int | None = None,
) -> tuple[int, int] | None:
    """Pick the most informative A/B pair for a set, or None if it isn't eligible. Informative =
    closest in current strength (outcome most uncertain) and least evidence so far, so verdicts go
    where they resolve the ranking fastest."""
    if owner_config_id is not None:
        state = owner_set_state(session, sub_group, owner_config_id)
        if state is not None and state.comparison_phase == "settled":
            return None
        ids = set_track_ids(session, sub_group)
        if len(ids) < settings.cover_comparison_min_covers:
            return None
        verdicts = _set_verdicts(session, sub_group, owner_config_id)
        if not verdicts:
            return (ids[0], ids[1]) if len(ids) >= 2 else None
        strengths = fit_strengths(ids, verdicts, prior_strength=settings.cover_bt_prior_strength)
        return _informative_pair(strengths, _verdict_counts(ids, verdicts), ids)

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

    strengths = {r.track_id: r.bt_strength for r in renditions}
    counts = {r.track_id: r.comparison_count for r in renditions}
    return _informative_pair(strengths, counts, [r.track_id for r in renditions])


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
    owner_config_id: int | None = None,
) -> dict[int, float]:
    """Append one A/B verdict and refit the set. Returns the refreshed strengths."""
    session.add(
        CoverComparison(
            sub_group=sub_group,
            owner_config_id=owner_config_id,
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
    return recompute_set(session, sub_group, settings, owner_config_id=owner_config_id)


def set_summary(
    session: Session,
    sub_group: str,
    settings: Settings,
    owner_config_id: int | None = None,
) -> tuple[str, int, list[tuple[int, float, int]]]:
    """``(comparison_phase, total_comparisons, [(track_id, bt_strength, comparison_count), ...])``
    for one cover set, ordered by strength desc. Legacy reads the shared cache; an owned profile
    derives strengths from its own verdicts and reads its phase from ``UserCoverSetState``."""
    if owner_config_id is None:
        renditions = session.scalars(
            select(CoverRenditionState)
            .where(CoverRenditionState.sub_group == sub_group)
            .order_by(CoverRenditionState.bt_strength.desc())
        ).all()
        state = session.get(CoverSetState, sub_group)
        rows = [(r.track_id, r.bt_strength, r.comparison_count) for r in renditions]
        return (
            state.comparison_phase if state else "stars",
            state.total_comparisons if state else 0,
            rows,
        )

    track_ids = set_track_ids(session, sub_group)
    verdicts = _set_verdicts(session, sub_group, owner_config_id)
    strengths = fit_strengths(track_ids, verdicts, prior_strength=settings.cover_bt_prior_strength)
    counts = _verdict_counts(track_ids, verdicts)
    state = owner_set_state(session, sub_group, owner_config_id)
    phase = state.comparison_phase if state else ("stars" if not verdicts else "bootstrapping")
    total = state.total_comparisons if state else len(verdicts)
    rows = sorted(
        ((tid, strengths.get(tid, 0.0), counts.get(tid, 0)) for tid in track_ids),
        key=lambda row: row[1],
        reverse=True,
    )
    return phase, total, rows


def rendition_states(
    session: Session,
    settings: Settings | None = None,
    owner_config_id: int | None = None,
) -> dict[int, CoverRenditionState]:
    """Rendition states keyed by track id for the generator. The legacy/unowned path reads the
    shared cache in one query; an owned profile recomputes (transient, unpersisted) states from its
    own verdicts so users never share a cover ranking."""
    if owner_config_id is None:
        return {row.track_id: row for row in session.scalars(select(CoverRenditionState))}

    prior = settings.cover_bt_prior_strength if settings is not None else 1.0
    sub_groups = set(
        session.scalars(
            select(CoverComparison.sub_group).where(
                CoverComparison.owner_config_id == owner_config_id
            )
        )
    )
    states: dict[int, CoverRenditionState] = {}
    for sub_group in sub_groups:
        track_ids = set_track_ids(session, sub_group)
        verdicts = _set_verdicts(session, sub_group, owner_config_id)
        strengths = fit_strengths(track_ids, verdicts, prior_strength=prior)
        counts = _verdict_counts(track_ids, verdicts)
        for track_id in track_ids:
            states[track_id] = CoverRenditionState(
                track_id=track_id,
                sub_group=sub_group,
                bt_strength=strengths.get(track_id, 0.0),
                comparison_count=counts.get(track_id, 0),
            )
    return states
