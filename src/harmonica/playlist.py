from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from harmonica.algorithm import (
    AlgorithmGroup,
    AlgorithmTrack,
    GeneratedItem,
    generate_playlist,
    write_jsonl_log,
)
from harmonica.config import Settings
from harmonica.db import engine
from harmonica.history import cold_start_multiplier, history_multiplier, summarize_history
from harmonica.models import (
    GroupMembership,
    MediaAsset,
    PlaylistItem,
    PlaylistRun,
    Track,
    TrackRating,
    WeightGroup,
    ensure_additive_playlist_run_columns,
)
from harmonica.ratings import aggregate_group_rating_multipliers, effective_song_multiplier


def load_algorithm_inputs(
    session: Session,
    settings: Settings,
) -> tuple[list[AlgorithmTrack], dict[int, AlgorithmGroup], object]:
    tracks = list(
        session.scalars(
            select(Track).options(
                selectinload(Track.assets),
                selectinload(Track.memberships).selectinload(GroupMembership.group),
                selectinload(Track.ratings).selectinload(TrackRating.factor),
            )
        )
    )
    variant_counts = dict(
        session.execute(
            select(Track.sub_group, func.count(Track.id))
            .where(Track.sub_group.is_not(None))
            .group_by(Track.sub_group)
        ).all()
    )
    history_summary = summarize_history(session, tracks, settings)
    groups = list(session.scalars(select(WeightGroup)))
    aggregate_group_multipliers = (
        aggregate_group_rating_multipliers(tracks, variant_counts, settings)
        if settings.enable_group_rating_multiplier
        else {}
    )
    group_map = {
        group.id: AlgorithmGroup(
            id=group.id,
            name=group.name,
            group_type=group.group_type,
            multiplier=group.manual_multiplier
            * (
                aggregate_group_multipliers.get(group.id, group.rating_multiplier)
                if settings.enable_group_rating_multiplier
                else 1.0
            ),
        )
        for group in groups
    }
    algorithm_tracks: list[AlgorithmTrack] = []
    for track in tracks:
        asset = preferred_asset(track)
        signal = history_summary.track_signals.get(track.id)
        variant_count = variant_counts.get(track.sub_group, 1) if track.sub_group else 1
        is_rated = track.id in history_summary.rated_track_ids
        algorithm_tracks.append(
            AlgorithmTrack(
                id=track.id,
                song_id=track.song_id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                media_asset_id=asset.id if asset else None,
                file_path=asset.file_path if asset else None,
                groups={membership.group_id: membership.share for membership in track.memberships},
                sub_group=track.sub_group,
                manual_multiplier=track.manual_multiplier,
                rating_multiplier=effective_song_multiplier(
                    track,
                    track.ratings,
                    variant_count,
                    settings,
                ),
                history_multiplier=history_multiplier(signal, settings),
                cold_start_multiplier=cold_start_multiplier(
                    track,
                    history_summary,
                    settings,
                    variant_count,
                ),
                has_video=any(asset.asset_type == "video" for asset in track.assets),
                repeat_count=signal.repeat_count if signal else 0.0,
                is_rated=is_rated,
            )
        )
    return algorithm_tracks, group_map, history_summary


def preferred_asset(track: Track) -> MediaAsset | None:
    if not track.assets:
        return None
    browser_assets = [asset for asset in track.assets if asset.browser_supported]
    candidates = browser_assets or list(track.assets)
    candidates.sort(key=lambda asset: (asset.asset_type != "audio", asset.id))
    return candidates[0]


def generate_and_persist_playlist(
    session: Session,
    settings: Settings,
    length: int,
    seed: str | int | None = None,
    write_debug_log: bool = True,
    ui_active: bool = False,
) -> tuple[PlaylistRun, list[GeneratedItem]]:
    ensure_additive_playlist_run_columns(engine)
    tracks, groups, history_summary = load_algorithm_inputs(session, settings)
    track_distances = {
        track_id: signal.repeat_distance
        for track_id, signal in history_summary.track_signals.items()
        if signal.repeat_distance is not None
    }
    track_repeat_credits = {
        track_id: signal.repeat_credit
        for track_id, signal in history_summary.track_signals.items()
        if signal.repeat_distance is not None
    }
    track_repeat_counts = {
        track_id: signal.repeat_count
        for track_id, signal in history_summary.track_signals.items()
    }
    items = generate_playlist(
        tracks,
        groups,
        length,
        settings,
        seed=seed,
        ui_active=ui_active,
        initial_track_distances=track_distances,
        initial_group_distances=history_summary.group_distances,
        initial_sub_group_distances=history_summary.sub_group_distances,
        initial_track_repeat_credits=track_repeat_credits,
        initial_group_repeat_credits=history_summary.group_repeat_credits,
        initial_sub_group_repeat_credits=history_summary.sub_group_repeat_credits,
        initial_track_repeat_counts=track_repeat_counts,
        cold_start_active=history_summary.cold_start_active,
    )
    run = PlaylistRun(
        seed=str(seed) if seed is not None else None,
        length=length,
        settings_json=json.dumps(settings_snapshot(settings)),
    )
    session.add(run)
    session.flush()
    for item in items:
        session.add(
            PlaylistItem(
                run=run,
                track_id=item.track.id,
                media_asset_id=item.track.media_asset_id,
                position=item.position,
                score=item.score,
                explanation_json=json.dumps(item.explanation),
            )
        )
    session.commit()
    session.refresh(run)
    if write_debug_log:
        log_path = settings.logs_path / "playlist-runs.jsonl"
        write_jsonl_log(
            log_path,
            {"run_id": run.id, "seed": run.seed, "length": run.length},
            items,
        )
    return run, items


def export_m3u8(items: list[GeneratedItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U"]
    for item in items:
        if item.track.file_path:
            lines.append(item.track.file_path)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def settings_snapshot(settings: Settings) -> dict[str, object]:
    return {
        "beta": settings.beta,
        "group_cooldown_floor": settings.group_cooldown_floor,
        "sub_group_cooldown_floor": settings.sub_group_cooldown_floor,
        "song_rating_min_multiplier": settings.song_rating_min_multiplier,
        "song_rating_max_multiplier": settings.song_rating_max_multiplier,
        "enable_group_rating_multiplier": settings.enable_group_rating_multiplier,
        "history_influence_enabled": settings.history_influence_enabled,
        "skip_penalty_strength": settings.skip_penalty_strength,
        "cold_start_enabled": settings.cold_start_enabled,
        "cold_start_unrated_boost": settings.cold_start_unrated_boost,
        "visual_priority_enabled": settings.visual_priority_enabled,
        "visual_priority_multiplier": settings.visual_priority_multiplier,
        "group_clustering_bias": settings.group_clustering_bias,
    }
