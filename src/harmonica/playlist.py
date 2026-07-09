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
from harmonica.bt import performance_multiplier
from harmonica.config import Settings
from harmonica.cover_ranking import rendition_states
from harmonica.db import engine
from harmonica.history import (
    cold_start_multiplier,
    history_multiplier,
    rediscovery_multiplier,
    satiation_multiplier,
    summarize_history,
)
from harmonica.models import (
    CoverRenditionState,
    GroupMembership,
    MediaAsset,
    PlaylistItem,
    PlaylistRun,
    Track,
    TrackRating,
    WeightGroup,
    ensure_additive_playlist_run_columns,
    now_utc,
)
from harmonica.normalization import (
    aggregate_group_multipliers_from_overall,
    compute_song_ratings,
)
from harmonica.ratings import (
    aggregate_group_rating_multipliers,
    effective_song_multiplier,
    rating_to_song_multiplier,
)


def load_algorithm_inputs(
    session: Session,
    settings: Settings,
    included_track_ids: set[int] | None = None,
    owner_config_id: int | None = None,
) -> tuple[list[AlgorithmTrack], dict[int, AlgorithmGroup], object]:
    all_tracks = list(
        session.scalars(
            select(Track).options(
                selectinload(Track.assets),
                selectinload(Track.memberships).selectinload(GroupMembership.group),
                selectinload(Track.ratings).selectinload(TrackRating.factor),
            )
        )
    )
    # A device config / user profile restricts the library to an explicit set of songs. The
    # candidate pool is always scoped to it; per-user listening/ratings/history are scoped to the
    # owner. A request with no owner (legacy/local) keeps the whole-library behaviour.
    tracks = (
        [track for track in all_tracks if track.id in included_track_ids]
        if included_track_ids is not None
        else all_tracks
    )
    # Per-user normalisation is calibrated to the owner's own library; legacy stays whole-library.
    ratings_tracks = tracks if owner_config_id is not None else all_tracks
    variant_counts = dict(
        session.execute(
            select(Track.sub_group, func.count(Track.id))
            .where(Track.sub_group.is_not(None))
            .group_by(Track.sub_group)
        ).all()
    )
    now = now_utc()
    history_summary = summarize_history(
        session, tracks, settings, now=now, owner_config_id=owner_config_id
    )
    groups = list(session.scalars(select(WeightGroup)))
    # Bradley-Terry rendition strengths (Phase D) only matter when two-level covers are on.
    cover_states = (
        rendition_states(session, settings, owner_config_id=owner_config_id)
        if settings.cover_two_level_enabled
        else {}
    )

    # Feature 1: normalised per-song rating (history-aware, mood-stripped). When disabled,
    # fall back to the legacy single-star path so behaviour is unchanged.
    song_ratings = (
        compute_song_ratings(
            session, ratings_tracks, variant_counts, settings, owner_config_id=owner_config_id
        )
        if settings.rating_normalization_enabled
        else None
    )
    # Library mean of the normalised overall — the bar a song must clear to count as a
    # "favourite" for rediscovery.
    library_overall_mean: float | None = None
    if song_ratings is not None:
        rated = [v for v in song_ratings.overall_by_track.values() if v is not None]
        library_overall_mean = sum(rated) / len(rated) if rated else None
    if not settings.enable_group_rating_multiplier:
        aggregate_group_multipliers = {}
    elif song_ratings is not None:
        aggregate_group_multipliers = aggregate_group_multipliers_from_overall(
            tracks, song_ratings.overall_by_track, settings
        )
    else:
        aggregate_group_multipliers = aggregate_group_rating_multipliers(
            tracks, variant_counts, settings
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
        # The per-song rating multiplier (normalised overall when enabled, else legacy). In the
        # two-level cover path this is also the unit-shared rating multiplier (covers.py averages
        # the renditions of a song), so song_rating_multiplier mirrors it for singletons.
        song_mult = (
            rating_to_song_multiplier(song_ratings.overall_by_track.get(track.id), settings)
            if song_ratings is not None
            else effective_song_multiplier(track, track.ratings, variant_count, settings)
        )
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
                favourite=bool(getattr(track, "favourite", False)),
                rating_multiplier=song_mult,
                song_rating_multiplier=song_mult,
                is_original_rendition=bool(getattr(track, "is_original_rendition", False)),
                perf_mult=cover_performance_multiplier(
                    track, settings, cover_states.get(track.id), owner_config_id=owner_config_id
                ),
                original_prior_mult=(
                    1.0 + settings.cover_original_bonus
                    if getattr(track, "is_original_rendition", False)
                    else 1.0
                ),
                history_multiplier=history_multiplier(signal, settings),
                cold_start_multiplier=cold_start_multiplier(
                    track,
                    history_summary,
                    settings,
                    variant_count,
                ),
                satiation_multiplier=satiation_multiplier(signal, settings),
                rediscovery_multiplier=rediscovery_multiplier(
                    signal,
                    song_ratings.overall_by_track.get(track.id) if song_ratings else None,
                    library_overall_mean,
                    now,
                    settings,
                ),
                has_video=any(asset.asset_type == "video" for asset in track.assets),
                repeat_count=signal.repeat_count if signal else 0.0,
                is_rated=is_rated,
                # Compressed = the asset we'd actually play is lossy (or unknown).
                is_compressed=bool(asset) and not asset.is_lossless,
            )
        )
    return algorithm_tracks, group_map, history_summary


def cover_performance_multiplier(
    track: Track,
    settings: Settings,
    rendition_state: CoverRenditionState | None = None,
    owner_config_id: int | None = None,
) -> float:
    """Within-set rendition preference: which rendition to play, never how often the song plays.

    Precedence: a learned Bradley-Terry strength from A/B verdicts (Phase D) > a directly-rated
    ``performance`` star (Phase C) > neutral (1.0). Bounded so a winning rendition can't take over.
    """
    if rendition_state is not None and rendition_state.comparison_count > 0:
        return performance_multiplier(
            rendition_state.bt_strength,
            settings.cover_perf_gamma,
            settings.cover_perf_min_multiplier,
            settings.cover_perf_max_multiplier,
        )
    # The directly-rated ``performance`` star lives on the shared/global rating cache, so only the
    # legacy/local (no-owner) path consults it; an owned profile relies on its own verdicts (above)
    # or stays neutral, never reading another user's star.
    if owner_config_id is None:
        for rating in track.ratings:
            if rating.factor and rating.factor.key == "performance" and rating.value is not None:
                return rating_to_song_multiplier(float(rating.value), settings)
    return 1.0


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
    included_track_ids: set[int] | None = None,
    owner_config_id: int | None = None,
) -> tuple[PlaylistRun, list[GeneratedItem]]:
    ensure_additive_playlist_run_columns(engine)
    tracks, groups, history_summary = load_algorithm_inputs(
        session, settings, included_track_ids, owner_config_id=owner_config_id
    )
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
    # A brand-new profile has an empty library: produce an empty run rather than letting the
    # generator try to draw from a zero-length candidate pool.
    items = (
        generate_playlist(
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
        if tracks
        else []
    )
    run = PlaylistRun(
        seed=str(seed) if seed is not None else None,
        length=length,
        settings_json=json.dumps(settings_snapshot(settings)),
        owner_config_id=owner_config_id,
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
        "skip_penalty_halflife": settings.skip_penalty_halflife,
        "rating_normalization_enabled": settings.rating_normalization_enabled,
        "rating_calibration_enabled": settings.rating_calibration_enabled,
        "satiation_enabled": settings.satiation_enabled,
        "satiation_strength": settings.satiation_strength,
        "satiation_window_days": settings.satiation_window_days,
        "rediscovery_enabled": settings.rediscovery_enabled,
        "rediscovery_strength": settings.rediscovery_strength,
        "rediscovery_halflife_days": settings.rediscovery_halflife_days,
        "favourite_pacing_enabled": settings.favourite_pacing_enabled,
        "favourite_pacing_strength": settings.favourite_pacing_strength,
        "why_show_math": settings.why_show_math,
        "cover_two_level_enabled": settings.cover_two_level_enabled,
        "cover_count_log_base": settings.cover_count_log_base,
        "cover_original_bonus": settings.cover_original_bonus,
    }
