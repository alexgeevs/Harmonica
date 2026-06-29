"""Two-level cover selection (Feature 2 / Phase C).

The legacy generator picks a track directly from one weighted pool. With covers enabled we instead:

  1. group every rendition of a song into a *unit* (its ``sub_group``; a song with no covers is its
     own singleton unit),
  2. pick a *unit* with weight ``W(u) = L(n) * SongRatingMult(u) * UnitCooldown(u) * Abar(u)`` where
     ``L(n) = 1 + log_base(n_covers)`` gives a song with many covers only a *logarithmic* edge, and
  3. pick a concrete rendition inside that unit by its per-cover weight.

``Abar`` is a v-weighted *average* (not a sum) of each cover's playback context, so cover count only
enters via the explicit ``L(n)`` term — 10 covers is ~2.66x a no-cover song, not 10x.

Backward compatibility: with no ``sub_group``s every unit is a singleton (``L(1)=1``, ``Abar=A_c``,
``UnitCooldown=1``, the within-unit pick is trivial and consumes no RNG draw), so ``W`` collapses to
the legacy score and a seeded run is byte-identical. See ``tests/test_covers.py``.
"""

from __future__ import annotations

import math
import random
from typing import Any

from harmonica.algorithm import (
    AlgorithmGroup,
    AlgorithmTrack,
    GeneratedItem,
    adjust_cooldown_for_repeat_credit,
    group_sizes,
    linear_recovery,
    score_track,
    weighted_choice,
)
from harmonica.config import Settings

SOLO_PREFIX = "__solo_"


def unit_key_for(track: AlgorithmTrack) -> str:
    """A song with covers shares its ``sub_group``; everything else is its own singleton unit."""
    if track.unit_key:
        return track.unit_key
    if track.sub_group:
        return track.sub_group
    return f"{SOLO_PREFIX}{track.id}"


def is_real_set(unit_key: str) -> bool:
    """A real cover set (gets the bounded unit cooldown) vs a singleton song (keeps the long
    song-level cooldown that already lives inside its per-cover context)."""
    return not unit_key.startswith(SOLO_PREFIX)


def cover_log_factor(n_covers: int, base: float) -> float:
    """``L(n) = 1 + log_base(n)``. ``L(1)=1`` so singletons are untouched; base clamped > 1 so a bad
    persisted setting can never divide by zero."""
    if n_covers <= 1:
        return 1.0
    base = max(base, 1.0000001)
    return 1.0 + math.log(n_covers) / math.log(base)


def _context_weight(explanation: dict[str, Any]) -> float:
    """A_c: a cover's playback context, deliberately EXCLUDING rating_multiplier (now unit-level via
    SongRatingMult) and sub_group_cooldown (now unit-level via UnitCooldown) to avoid double-count.
    Everything else that shapes how often *this exact rendition* should play stays in."""
    return (
        explanation["base_score"]
        * explanation["manual_multiplier"]
        * explanation["history_multiplier"]
        * explanation["cold_start_multiplier"]
        * explanation["satiation_multiplier"]
        * explanation["rediscovery_multiplier"]
        * explanation["visual_multiplier"]
        * explanation["song_cooldown"]
    )


def _finite(value: float) -> float:
    return value if math.isfinite(value) and value > 0 else 0.0


class _Unit:
    """Static per-unit structure, built once per generation."""

    __slots__ = ("key", "members", "n_covers", "song_rating_mult", "v", "real")

    def __init__(self, key: str, members: list[int], tracks: list[AlgorithmTrack]) -> None:
        self.key = key
        self.members = members  # indices into `tracks`
        self.n_covers = len(members)
        rating_mults = [tracks[i].song_rating_multiplier for i in members]
        self.song_rating_mult = sum(rating_mults) / len(rating_mults) if rating_mults else 1.0
        # v_c = how much we prefer this rendition *within* the set (never how often the song plays).
        self.v = {i: max(tracks[i].perf_mult * tracks[i].original_prior_mult, 0.0) for i in members}
        self.real = is_real_set(key)


def build_units(tracks: list[AlgorithmTrack]) -> list[_Unit]:
    """Group tracks into units, preserving first-appearance order (so a singleton library yields
    units in the same order as the tracks — required for seeded parity)."""
    order: list[str] = []
    members: dict[str, list[int]] = {}
    for index, track in enumerate(tracks):
        key = unit_key_for(track)
        if key not in members:
            members[key] = []
            order.append(key)
        members[key].append(index)
    return [_Unit(key, members[key], tracks) for key in order]


def cold_start_candidate_units(
    units: list[_Unit],
    tracks: list[AlgorithmTrack],
    track_repeat_counts: dict[int, float],
    settings: Settings,
    cold_start_active: bool,
) -> tuple[list[int] | None, str]:
    """Unit-level cold start: a unit needs coverage if any rendition is unplayed+unrated; it leaves
    first-coverage after a single play of the song (matching the user's song-level intent)."""
    if not settings.cold_start_enabled or not cold_start_active:
        return None, "off"

    def uncovered(unit: _Unit) -> bool:
        return any(
            track_repeat_counts.get(tracks[i].id, 0.0) < 1.0 and not tracks[i].is_rated
            for i in unit.members
        )

    first = [ui for ui, unit in enumerate(units) if uncovered(unit)]
    if first:
        return first, "first_coverage"

    def unit_plays(unit: _Unit) -> float:
        return sum(track_repeat_counts.get(tracks[i].id, 0.0) for i in unit.members)

    played_twice = sum(1 for unit in units if unit_plays(unit) >= 2.0)
    if played_twice < (len(units) / 2):
        second = [ui for ui, unit in enumerate(units) if unit_plays(unit) < 2.0]
        if second:
            return second, "second_coverage"
    return None, "complete"


def generate_playlist_two_level(
    tracks: list[AlgorithmTrack],
    groups: dict[int, AlgorithmGroup],
    length: int,
    settings: Settings,
    seed: str | int | None = None,
    ui_active: bool = False,
    initial_track_distances: dict[int, int] | None = None,
    initial_group_distances: dict[int, int] | None = None,
    initial_sub_group_distances: dict[str, int] | None = None,
    initial_track_repeat_credits: dict[int, float] | None = None,
    initial_group_repeat_credits: dict[int, float] | None = None,
    initial_sub_group_repeat_credits: dict[str, float] | None = None,
    initial_track_repeat_counts: dict[int, float] | None = None,
    cold_start_active: bool = False,
) -> list[GeneratedItem]:
    if not tracks:
        return []

    rng = random.Random(seed)
    sizes = group_sizes(tracks, groups)
    units = build_units(tracks)
    total = len(tracks)
    sub_horizon = min(30, max(total, 1))
    log_base = settings.cover_count_log_base

    track_last_played = {track.id: -(10**9) for track in tracks}
    for track_id, distance in (initial_track_distances or {}).items():
        track_last_played[track_id] = -max(distance, 0)
    group_last_played = {
        group_id: -max(distance, 0)
        for group_id, distance in (initial_group_distances or {}).items()
    }
    sub_group_last_played = {
        sub_group: -max(distance, 0)
        for sub_group, distance in (initial_sub_group_distances or {}).items()
    }
    track_repeat_credits = dict(initial_track_repeat_credits or {})
    group_repeat_credits = dict(initial_group_repeat_credits or {})
    sub_group_repeat_credits = dict(initial_sub_group_repeat_credits or {})
    track_repeat_counts = {track.id: max(track.repeat_count, 0.0) for track in tracks}
    for track_id, repeat_count in (initial_track_repeat_counts or {}).items():
        track_repeat_counts[track_id] = max(repeat_count, 0.0)

    output: list[GeneratedItem] = []
    prev_compressed = False

    def score_all(disable_groups_sub: bool, disable_song: bool) -> list[tuple[float, dict]]:
        return [
            score_track(
                track,
                groups,
                sizes,
                settings,
                position,
                track_last_played,
                group_last_played,
                sub_group_last_played,
                track_repeat_credits,
                group_repeat_credits,
                sub_group_repeat_credits,
                ui_active=ui_active,
                disable_group_and_sub_cooldowns=disable_groups_sub,
                disable_song_cooldown=disable_song,
            )
            for track in tracks
        ]

    def unit_cooldown(unit: _Unit, disable: bool) -> float:
        if disable or not unit.real:
            return 1.0
        last = sub_group_last_played.get(unit.key)
        distance = None if last is None else position - last
        cooldown = linear_recovery(distance, sub_horizon, settings.sub_group_cooldown_floor)
        return adjust_cooldown_for_repeat_credit(
            cooldown, sub_group_repeat_credits.get(unit.key, 1.0)
        )

    def compute(disable_groups_sub: bool, disable_song: bool) -> tuple[
        list[tuple[float, dict]], list[float], list[float]
    ]:
        """Returns (scored, W_raw_by_unit, W_sel_by_unit). W_sel adds the consecutive-compressed
        soft-bias (selection only); W_raw is used for the stored item score."""
        scored = score_all(disable_groups_sub, disable_song)
        a_raw = [_context_weight(ex) for _, ex in scored]
        a_sel = list(a_raw)
        if settings.avoid_consecutive_compressed and prev_compressed:
            a_sel = [
                (value * 0.5 if tracks[i].is_compressed else value)
                for i, value in enumerate(a_sel)
            ]
        w_raw: list[float] = []
        w_sel: list[float] = []
        for unit in units:
            log_factor = cover_log_factor(unit.n_covers, log_base)
            cooldown = unit_cooldown(unit, disable_groups_sub)
            v_total = sum(unit.v[i] for i in unit.members)

            def abar(a: list[float], unit: _Unit = unit, v_total: float = v_total) -> float:
                if v_total <= 0:
                    return 0.0
                return sum(a[i] * unit.v[i] for i in unit.members) / v_total

            shared = log_factor * unit.song_rating_mult * cooldown
            w_raw.append(_finite(shared * abar(a_raw)))
            w_sel.append(_finite(shared * abar(a_sel)))
        return scored, w_raw, w_sel

    for position in range(length):
        fallback = "normal"
        candidate_units, cold_start_pool = cold_start_candidate_units(
            units, tracks, track_repeat_counts, settings, cold_start_active
        )
        choice_unit_indices = candidate_units or list(range(len(units)))

        scored, w_raw, w_sel = compute(False, False)
        if sum(w_sel[ui] for ui in choice_unit_indices) <= 0:
            fallback = "ignored_group_and_subgroup_cooldowns"
            scored, w_raw, w_sel = compute(True, False)
        if sum(w_sel[ui] for ui in choice_unit_indices) <= 0:
            fallback = "ignored_all_cooldowns"
            scored, w_raw, w_sel = compute(True, True)

        chosen_unit, chosen_unit_index = weighted_choice_among(
            rng, units, w_sel, choice_unit_indices
        )

        # Within the chosen unit, pick a concrete rendition. A singleton consumes NO rng draw, which
        # keeps the seeded sequence identical to the legacy single-pool generator.
        members = chosen_unit.members
        in_first_coverage = cold_start_pool == "first_coverage"
        if len(members) == 1:
            chosen_index = members[0]
        else:
            pick_from = members
            if in_first_coverage:
                uncovered = [
                    i
                    for i in members
                    if track_repeat_counts.get(tracks[i].id, 0.0) < 1.0 and not tracks[i].is_rated
                ]
                pick_from = uncovered or members
            # The song's frequency uses the SHARED (averaged) rating; here, after the song is
            # chosen, the pick between renditions also weighs each cover's OWN individual rating
            # (computed but never shown to the user) on top of performance + the original nudge.
            # song_rating_multiplier holds each rendition's individual overall — the unit averaged
            # these for its shared frequency weight, so reading it here adds no frequency bias.
            cover_weights = [
                _finite(
                    (
                        _context_weight(scored[i][1])
                        * chosen_unit.v[i]
                        * tracks[i].song_rating_multiplier
                    )
                    * (0.5 if settings.avoid_consecutive_compressed
                       and prev_compressed and tracks[i].is_compressed else 1.0)
                )
                for i in pick_from
            ]
            _, local = weighted_choice(rng, [tracks[i] for i in pick_from], cover_weights)
            chosen_index = pick_from[local]

        chosen = tracks[chosen_index]
        explanation = dict(scored[chosen_index][1])
        explanation["fallback"] = fallback
        explanation["cold_start_pool"] = cold_start_pool
        explanation["eligible_candidate_count"] = len(choice_unit_indices)
        explanation["position"] = position
        explanation["unit_key"] = chosen_unit.key
        explanation["n_covers"] = chosen_unit.n_covers
        explanation["cover_log_factor"] = cover_log_factor(chosen_unit.n_covers, log_base)
        explanation["song_rating"] = chosen_unit.song_rating_mult
        explanation["cover_performance"] = chosen.perf_mult
        explanation["original_prior"] = chosen.original_prior_mult
        explanation["unit_weight"] = w_raw[chosen_unit_index]
        explanation["top_candidates"] = top_units(units, w_raw, tracks)

        output.append(
            GeneratedItem(
                position=position,
                track=chosen,
                score=scored[chosen_index][0],
                explanation=explanation,
            )
        )

        track_last_played[chosen.id] = position
        track_repeat_credits[chosen.id] = 1.0
        track_repeat_counts[chosen.id] = track_repeat_counts.get(chosen.id, 0.0) + 1.0
        for group_id in chosen.groups:
            group_last_played[group_id] = position
            group_repeat_credits[group_id] = 1.0
        if chosen_unit.real:
            sub_group_last_played[chosen_unit.key] = position
            sub_group_repeat_credits[chosen_unit.key] = 1.0
        prev_compressed = chosen.is_compressed

    return output


def weighted_choice_among(
    rng: random.Random,
    units: list[_Unit],
    weights: list[float],
    indices: list[int],
) -> tuple[_Unit, int]:
    """Like algorithm.weighted_choice_from_indices but over units; returns (unit, global index)."""
    indexed_units = [units[i] for i in indices]
    indexed_weights = [weights[i] for i in indices]
    chosen, local = weighted_choice(rng, indexed_units, indexed_weights)
    return chosen, indices[local]


def top_units(
    units: list[_Unit],
    weights: list[float],
    tracks: list[AlgorithmTrack],
    limit: int = 8,
) -> list[dict[str, Any]]:
    rows = [
        {
            "unit_key": unit.key,
            "title": tracks[unit.members[0]].title,
            "n_covers": unit.n_covers,
            "score": weights[index],
        }
        for index, unit in enumerate(units)
    ]
    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows[:limit]
