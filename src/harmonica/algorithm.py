from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harmonica.config import Settings


@dataclass(frozen=True)
class AlgorithmGroup:
    id: int
    name: str
    group_type: str
    multiplier: float = 1.0


@dataclass(frozen=True)
class AlgorithmTrack:
    id: int
    song_id: str
    title: str
    artist: str | None
    album: str | None
    media_asset_id: int | None
    file_path: str | None
    groups: dict[int, float | None] = field(default_factory=dict)
    sub_group: str | None = None
    manual_multiplier: float = 1.0
    rating_multiplier: float = 1.0
    history_multiplier: float = 1.0
    cold_start_multiplier: float = 1.0
    has_video: bool = False


@dataclass
class GeneratedItem:
    position: int
    track: AlgorithmTrack
    score: float
    explanation: dict[str, Any]


def linear_recovery(distance: int | None, horizon: int, floor: float = 0.0) -> float:
    if distance is None:
        return 1.0
    if horizon <= 0:
        return 1.0
    if distance <= 0:
        return floor
    if distance >= horizon:
        return 1.0
    return floor + (1.0 - floor) * (distance / horizon)


def normalized_membership_shares(track: AlgorithmTrack) -> dict[int, float]:
    if not track.groups:
        return {}
    explicit = {group_id: share for group_id, share in track.groups.items() if share is not None}
    explicit_total = sum(max(0.0, share or 0.0) for share in explicit.values())
    if explicit and explicit_total > 0:
        return {
            group_id: max(0.0, share or 0.0) / explicit_total
            for group_id, share in explicit.items()
        }
    equal_share = 1.0 / len(track.groups)
    return {group_id: equal_share for group_id in track.groups}


def weighted_choice(
    rng: random.Random,
    items: list[AlgorithmTrack],
    scores: list[float],
) -> tuple[AlgorithmTrack, int]:
    total = sum(scores)
    if total <= 0:
        index = rng.randrange(len(items))
        return items[index], index
    threshold = rng.random() * total
    cumulative = 0.0
    for index, score in enumerate(scores):
        cumulative += score
        if cumulative >= threshold:
            return items[index], index
    return items[-1], len(items) - 1


def group_sizes(tracks: list[AlgorithmTrack], groups: dict[int, AlgorithmGroup]) -> dict[int, int]:
    sizes = {group_id: 0 for group_id in groups}
    for track in tracks:
        for group_id in track.groups:
            if group_id in sizes:
                sizes[group_id] += 1
    return sizes


def adjust_cooldown_for_repeat_credit(cooldown: float, repeat_credit: float) -> float:
    bounded_credit = min(max(repeat_credit, 0.0), 1.0)
    return 1.0 - bounded_credit * (1.0 - cooldown)


def apply_clustering_bias(
    cooldown: float,
    distance: int | None,
    horizon: int,
    settings: Settings,
) -> float:
    bias = min(max(settings.group_clustering_bias, -1.0), 1.0)
    if bias == 0 or distance is None or horizon <= 0 or distance >= horizon:
        return cooldown
    proximity = max(0.0, 1.0 - (max(distance, 0) / horizon))
    if bias > 0:
        return min(2.0, cooldown + (bias * proximity))
    return max(0.0, cooldown * (1.0 + (bias * 0.5 * proximity)))


def score_track(
    track: AlgorithmTrack,
    groups: dict[int, AlgorithmGroup],
    sizes: dict[int, int],
    settings: Settings,
    current_index: int,
    track_last_played: dict[int, int],
    group_last_played: dict[int, int],
    sub_group_last_played: dict[str, int],
    track_repeat_credits: dict[int, float] | None = None,
    group_repeat_credits: dict[int, float] | None = None,
    sub_group_repeat_credits: dict[str, float] | None = None,
    ui_active: bool = False,
    disable_group_and_sub_cooldowns: bool = False,
    disable_song_cooldown: bool = False,
) -> tuple[float, dict[str, Any]]:
    track_repeat_credits = track_repeat_credits or {}
    group_repeat_credits = group_repeat_credits or {}
    sub_group_repeat_credits = sub_group_repeat_credits or {}
    total_tracks = max(len(track_last_played), 1)
    shares = normalized_membership_shares(track)
    group_count = max(len(groups), 1)
    group_horizon = min(group_count, 12)
    group_contributions: list[dict[str, Any]] = []

    if not shares:
        base_score = 1.0
    else:
        base_score = 0.0
        for group_id, share in shares.items():
            group = groups.get(group_id)
            if group is None:
                continue
            size = max(sizes.get(group_id, 0), 1)
            distance = (
                None
                if group_id not in group_last_played
                else current_index - group_last_played[group_id]
            )
            cooldown = (
                1.0
                if disable_group_and_sub_cooldowns
                else linear_recovery(distance, group_horizon, settings.group_cooldown_floor)
            )
            cooldown = adjust_cooldown_for_repeat_credit(
                cooldown, group_repeat_credits.get(group_id, 1.0)
            )
            if not disable_group_and_sub_cooldowns:
                cooldown = apply_clustering_bias(cooldown, distance, group_horizon, settings)
            group_weight = group.multiplier * (1.0 + settings.beta * math.log(size))
            contribution = share * (group_weight / size) * cooldown
            base_score += contribution
            group_contributions.append(
                {
                    "group_id": group_id,
                    "name": group.name,
                    "share": share,
                    "size": size,
                    "multiplier": group.multiplier,
                    "cooldown": cooldown,
                    "contribution": contribution,
                }
            )

    song_distance = (
        None if track.id not in track_last_played else current_index - track_last_played[track.id]
    )
    song_horizon = max(total_tracks, 1)
    song_cooldown = (
        1.0 if disable_song_cooldown else linear_recovery(song_distance, song_horizon, 0.0)
    )
    song_cooldown = adjust_cooldown_for_repeat_credit(
        song_cooldown, track_repeat_credits.get(track.id, 1.0)
    )

    sub_cooldown = 1.0
    if track.sub_group:
        sub_distance = (
            None
            if track.sub_group not in sub_group_last_played
            else current_index - sub_group_last_played[track.sub_group]
        )
        sub_horizon = min(30, max(total_tracks, 1))
        sub_cooldown = (
            1.0
            if disable_group_and_sub_cooldowns
            else linear_recovery(sub_distance, sub_horizon, settings.sub_group_cooldown_floor)
        )
        sub_cooldown = adjust_cooldown_for_repeat_credit(
            sub_cooldown, sub_group_repeat_credits.get(track.sub_group, 1.0)
        )

    visual_multiplier = (
        settings.visual_priority_multiplier
        if ui_active and settings.visual_priority_enabled and track.has_video
        else 1.0
    )

    final_score = (
        base_score
        * track.manual_multiplier
        * track.rating_multiplier
        * track.history_multiplier
        * track.cold_start_multiplier
        * visual_multiplier
        * song_cooldown
        * sub_cooldown
    )
    explanation = {
        "track_id": track.id,
        "song_id": track.song_id,
        "title": track.title,
        "base_score": base_score,
        "manual_multiplier": track.manual_multiplier,
        "rating_multiplier": track.rating_multiplier,
        "history_multiplier": track.history_multiplier,
        "cold_start_multiplier": track.cold_start_multiplier,
        "visual_multiplier": visual_multiplier,
        "song_cooldown": song_cooldown,
        "sub_group_cooldown": sub_cooldown,
        "group_contributions": group_contributions,
        "score": max(0.0, final_score),
    }
    return max(0.0, final_score), explanation


def generate_playlist(
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
) -> list[GeneratedItem]:
    if not tracks:
        return []

    rng = random.Random(seed)
    sizes = group_sizes(tracks, groups)
    track_last_played = {track.id: -10**9 for track in tracks}
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
    output: list[GeneratedItem] = []

    for position in range(length):
        fallback = "normal"
        scored = [
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
            )
            for track in tracks
        ]
        scores = [score for score, _ in scored]
        if sum(scores) <= 0:
            fallback = "ignored_group_and_subgroup_cooldowns"
            scored = [
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
                    disable_group_and_sub_cooldowns=True,
                )
                for track in tracks
            ]
            scores = [score for score, _ in scored]
        if sum(scores) <= 0:
            fallback = "ignored_all_cooldowns"
            scored = [
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
                    disable_group_and_sub_cooldowns=True,
                    disable_song_cooldown=True,
                )
                for track in tracks
            ]
            scores = [score for score, _ in scored]

        chosen, chosen_index = weighted_choice(rng, tracks, scores)
        explanation = scored[chosen_index][1]
        explanation["fallback"] = fallback
        explanation["position"] = position
        explanation["top_candidates"] = top_candidates(tracks, scored)
        output.append(
            GeneratedItem(
                position=position,
                track=chosen,
                score=scores[chosen_index],
                explanation=explanation,
            )
        )

        track_last_played[chosen.id] = position
        track_repeat_credits[chosen.id] = 1.0
        for group_id in chosen.groups:
            group_last_played[group_id] = position
            group_repeat_credits[group_id] = 1.0
        if chosen.sub_group:
            sub_group_last_played[chosen.sub_group] = position
            sub_group_repeat_credits[chosen.sub_group] = 1.0

    return output


def top_candidates(
    tracks: list[AlgorithmTrack],
    scored: list[tuple[float, dict[str, Any]]],
    limit: int = 8,
) -> list[dict[str, Any]]:
    rows = [
        {
            "track_id": track.id,
            "song_id": track.song_id,
            "title": track.title,
            "score": score,
        }
        for track, (score, _) in zip(tracks, scored, strict=True)
    ]
    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows[:limit]


def write_jsonl_log(path: Path, run_payload: dict[str, Any], items: list[GeneratedItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": "playlist_run", **run_payload}) + "\n")
        for item in items:
            handle.write(json.dumps({"event": "playlist_item", **item.explanation}) + "\n")
