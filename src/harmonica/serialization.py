from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from harmonica.config import Settings, get_settings
from harmonica.cover_ranking import recompute_set
from harmonica.embeds import parse_embed_url
from harmonica.models import (
    CooldownTag,
    CoverComparison,
    DeviceConfigTrack,
    Embed,
    GroupMembership,
    MediaAsset,
    RatingFactor,
    RatingSample,
    Track,
    TrackCooldownTag,
    TrackRating,
    WeightGroup,
    favourite_track_ids,
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _finite(value: Any, default: float) -> float:
    """Coerce to a finite float, falling back to ``default`` for None/NaN/inf/garbage.

    Imported library data is untrusted: this keeps NaN/inf out of the scoring maths
    (where they would poison or crash queue generation)."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _clamp_rating(value: Any) -> float | None:
    """Sanitise an imported star value to the same [0, 5] range the live PATCH path
    enforces; preserve an explicit ``None`` (unrated)."""
    if value is None:
        return None
    return min(max(_finite(value, 0.0), 0.0), 5.0)


def export_library(session: Session, output_path: Path) -> None:
    payload = export_library_payload(session)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_library_payload(
    session: Session, owner_config_id: int | None = None
) -> dict[str, Any]:
    track_select = select(Track).options(
        selectinload(Track.assets),
        selectinload(Track.embeds),
        selectinload(Track.memberships).selectinload(GroupMembership.group),
        selectinload(Track.ratings).selectinload(TrackRating.factor),
        selectinload(Track.cooldown_tags).selectinload(TrackCooldownTag.tag),
    )
    if owner_config_id is not None:
        # An owned export carries only that profile's own library (privacy: never another user's).
        track_select = track_select.join(
            DeviceConfigTrack, DeviceConfigTrack.track_id == Track.id
        ).where(DeviceConfigTrack.config_id == owner_config_id)
    tracks = list(session.scalars(track_select))
    # Favourites are per-profile: an owned export carries the exporting profile's own tags.
    owner_favourites = (
        favourite_track_ids(session, owner_config_id) if owner_config_id is not None else None
    )
    groups = list(session.scalars(select(WeightGroup)))
    factors = list(session.scalars(select(RatingFactor)))
    return {
        "rating_factors": [
            {
                "key": factor.key,
                "label": factor.label,
                "weight": factor.weight,
                "applies_to_lyrics": factor.applies_to_lyrics,
                "applies_to_instrumental": factor.applies_to_instrumental,
                "applies_to_variants_only": factor.applies_to_variants_only,
                "enabled": factor.enabled,
            }
            for factor in factors
        ],
        "groups": [
            {
                "name": group.name,
                "group_type": group.group_type,
                "manual_multiplier": group.manual_multiplier,
                "rating_multiplier": group.rating_multiplier,
            }
            for group in groups
        ],
        "tracks": [
            track_to_payload(
                track,
                favourite=(track.id in owner_favourites)
                if owner_favourites is not None
                else None,
            )
            for track in tracks
        ],
        # Raw, append-only history the algorithm derives from. Keyed by song_id/factor_key so it
        # survives a move to another device (where local row ids differ). Device-local session/run
        # ids are stripped — they have no meaning on the destination.
        "rating_samples": rating_samples_payload(session, owner_config_id=owner_config_id),
        "cover_comparisons": cover_comparisons_payload(session, owner_config_id=owner_config_id),
    }


def rating_samples_payload(
    session: Session, owner_config_id: int | None = None
) -> list[dict[str, Any]]:
    song_by_id = dict(session.execute(select(Track.id, Track.song_id)).all())
    key_by_id = dict(session.execute(select(RatingFactor.id, RatingFactor.key)).all())
    out: list[dict[str, Any]] = []
    sample_select = select(RatingSample).order_by(RatingSample.created_at)
    if owner_config_id is not None:
        sample_select = sample_select.where(RatingSample.owner_config_id == owner_config_id)
    else:
        sample_select = sample_select.where(RatingSample.owner_config_id.is_(None))
    for row in session.scalars(sample_select):
        song_id = song_by_id.get(row.track_id)
        factor_key = key_by_id.get(row.factor_id)
        if song_id is None or factor_key is None:
            continue
        out.append(
            {
                "song_id": song_id,
                "factor_key": factor_key,
                "value": row.value,
                "source": row.source,
                "created_at": _iso(row.created_at),
            }
        )
    return out


def cover_comparisons_payload(
    session: Session, owner_config_id: int | None = None
) -> list[dict[str, Any]]:
    song_by_id = dict(session.execute(select(Track.id, Track.song_id)).all())
    out: list[dict[str, Any]] = []
    comparison_select = select(CoverComparison).order_by(CoverComparison.created_at)
    if owner_config_id is not None:
        comparison_select = comparison_select.where(
            CoverComparison.owner_config_id == owner_config_id
        )
    else:
        comparison_select = comparison_select.where(CoverComparison.owner_config_id.is_(None))
    for row in session.scalars(comparison_select):
        song_a = song_by_id.get(row.track_a_id)
        song_b = song_by_id.get(row.track_b_id)
        if song_a is None or song_b is None:
            continue
        out.append(
            {
                "sub_group": row.sub_group,
                "song_id_a": song_a,
                "song_id_b": song_b,
                "winner_song_id": song_by_id.get(row.winner_track_id)
                if row.winner_track_id is not None
                else None,
                "pct_a": row.pct_a,
                "pct_b": row.pct_b,
                "created_at": _iso(row.created_at),
            }
        )
    return out


def import_library(session: Session, input_path: Path) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    import_library_payload(session, payload)


def _find_existing_track(session: Session, track_payload: dict[str, Any]) -> Track | None:
    """Resolve an incoming track to one already in the shared pool: by ``song_id``, then by any
    asset ``checksum`` (same file content), then by ``file_path``. Enables dedupe-and-redirect so a
    second user importing the same song reuses the existing track/file."""
    track = session.scalar(select(Track).where(Track.song_id == track_payload["song_id"]))
    if track is not None:
        return track
    for asset in track_payload.get("assets", []):
        checksum = asset.get("checksum")
        if checksum:
            existing = session.scalar(select(MediaAsset).where(MediaAsset.checksum == checksum))
            if existing is not None:
                return existing.track
        file_path = asset.get("file_path")
        if file_path:
            existing = session.scalar(select(MediaAsset).where(MediaAsset.file_path == file_path))
            if existing is not None:
                return existing.track
    return None


def _link_owner(
    session: Session,
    owner_config_id: int | None,
    track_id: int,
    favourite: bool | None = None,
) -> None:
    """Add the track to the owner's private library (idempotent). No-op for legacy/local import.
    When ``favourite`` is given, stamp the profile's private favourite tag onto the link."""
    if owner_config_id is None:
        return
    link = session.scalar(
        select(DeviceConfigTrack).where(
            DeviceConfigTrack.config_id == owner_config_id,
            DeviceConfigTrack.track_id == track_id,
        )
    )
    if link is None:
        link = DeviceConfigTrack(config_id=owner_config_id, track_id=track_id)
        session.add(link)
    if favourite is not None:
        link.favourite = favourite


def import_library_payload(
    session: Session,
    payload: dict[str, Any],
    settings: Settings | None = None,
    owner_config_id: int | None = None,
) -> None:
    factor_map = upsert_rating_factors(session, payload.get("rating_factors", []))
    group_map = upsert_groups(session, payload.get("groups", []))

    for track_payload in payload.get("tracks", []):
        track = _find_existing_track(session, track_payload)
        is_new = track is None
        if is_new:
            track = Track(
                song_id=track_payload["song_id"],
                title=track_payload.get("title") or "Untitled",
            )
            session.add(track)
            session.flush()

        # Shared content (metadata, assets, groups, tags) is written only when this import is
        # CREATING the track, or when it's a legacy/local (no-owner) import. An owned import that
        # matched an existing shared track just links to it — never overwriting another user's data.
        if is_new or owner_config_id is None:
            track.title = track_payload.get("title") or track.title
            track.artist = track_payload.get("artist")
            track.album = track_payload.get("album")
            track.has_lyrics = bool(track_payload.get("has_lyrics", True))
            track.sub_group = track_payload.get("sub_group")
            track.manual_multiplier = _finite(track_payload.get("manual_multiplier", 1.0), 1.0)
            if "is_original_rendition" in track_payload:
                track.is_original_rendition = bool(track_payload.get("is_original_rendition"))
            if "clip_start_seconds" in track_payload:
                track.clip_start_seconds = track_payload.get("clip_start_seconds")
            if "clip_end_seconds" in track_payload:
                track.clip_end_seconds = track_payload.get("clip_end_seconds")
            if "audio_only" in track_payload:
                track.audio_only = bool(track_payload.get("audio_only"))

            for asset_payload in track_payload.get("assets", []):
                upsert_asset(session, track, asset_payload)
            for embed_payload in track_payload.get("embeds", []):
                _upsert_embed(session, track, embed_payload)
            for membership_payload in track_payload.get("groups", []):
                group_name = membership_payload["name"]
                group = group_map.get(group_name)
                if group is None:
                    group = WeightGroup(
                        name=group_name,
                        group_type=membership_payload.get("group_type", "other"),
                    )
                    session.add(group)
                    session.flush()
                    group_map[group.name] = group
                membership = session.scalar(
                    select(GroupMembership).where(
                        GroupMembership.track_id == track.id,
                        GroupMembership.group_id == group.id,
                    )
                )
                if membership is None:
                    membership = GroupMembership(track=track, group=group)
                    session.add(membership)
                membership.share = membership_payload.get("share")
            for tag_name in track_payload.get("cooldown_tags", []):
                upsert_track_tag(session, track, tag_name)

        # The shared latest-star cache is legacy-only; an owned profile's ratings ride in
        # rating_samples (owner-stamped below), never in the shared TrackRating rows.
        if owner_config_id is None:
            for rating_key, value in track_payload.get("ratings", {}).items():
                factor = factor_map.get(rating_key)
                if factor is None:
                    continue
                rating = session.scalar(
                    select(TrackRating).where(
                        TrackRating.track_id == track.id,
                        TrackRating.factor_id == factor.id,
                    )
                )
                if rating is None:
                    rating = TrackRating(track=track, factor=factor)
                    session.add(rating)
                rating.value = _clamp_rating(value)

        # Favourite is a per-user opinion: for a legacy import it rides on the shared Track; for an
        # owned import it stamps the profile's private link (never the shared column).
        fav_value = (
            bool(track_payload["favourite"]) if "favourite" in track_payload else None
        )
        if owner_config_id is None and fav_value is not None:
            track.favourite = fav_value
        _link_owner(session, owner_config_id, track.id, favourite=fav_value)
    session.flush()

    import_rating_samples(
        session, payload.get("rating_samples", []), factor_map, owner_config_id=owner_config_id
    )
    affected_sets = import_cover_comparisons(
        session, payload.get("cover_comparisons", []), owner_config_id=owner_config_id
    )
    # Caches (Bradley-Terry strengths / set phase) are NEVER trusted from an export — they're
    # recomputed from the raw verdicts we just imported, so they're always self-consistent here.
    resolved_settings = settings or get_settings()
    for sub_group in affected_sets:
        recompute_set(session, sub_group, resolved_settings, owner_config_id=owner_config_id)
    session.commit()


def import_rating_samples(
    session: Session,
    payloads: list[dict[str, Any]],
    factor_map: dict[str, RatingFactor],
    owner_config_id: int | None = None,
) -> None:
    track_by_song = {track.song_id: track for track in session.scalars(select(Track))}
    # The owner is part of the idempotency key, so re-importing under one profile won't duplicate,
    # yet two different profiles can each hold their own copy of the same history.
    seen = {
        (row.owner_config_id, row.track_id, row.factor_id, row.value, _iso(row.created_at))
        for row in session.scalars(select(RatingSample))
    }
    for entry in payloads:
        track = track_by_song.get(entry.get("song_id"))
        factor = factor_map.get(entry.get("factor_key"))
        if track is None or factor is None:
            continue
        created_at = _parse_iso(entry.get("created_at"))
        value = _clamp_rating(entry.get("value"))
        key = (owner_config_id, track.id, factor.id, value, _iso(created_at))
        if key in seen:
            continue  # idempotent: re-importing the same export won't duplicate history
        seen.add(key)
        sample = RatingSample(
            track_id=track.id,
            factor_id=factor.id,
            value=value,
            source=entry.get("source", "import"),
            owner_config_id=owner_config_id,
        )
        if created_at is not None:
            sample.created_at = created_at
        session.add(sample)


def import_cover_comparisons(
    session: Session,
    payloads: list[dict[str, Any]],
    owner_config_id: int | None = None,
) -> set[str]:
    track_by_song = {track.song_id: track for track in session.scalars(select(Track))}
    seen = {
        (row.owner_config_id, row.sub_group, row.track_a_id, row.track_b_id, _iso(row.created_at))
        for row in session.scalars(select(CoverComparison))
    }
    affected: set[str] = set()
    for entry in payloads:
        track_a = track_by_song.get(entry.get("song_id_a"))
        track_b = track_by_song.get(entry.get("song_id_b"))
        sub_group = entry.get("sub_group")
        if track_a is None or track_b is None or not sub_group:
            continue
        winner_song = entry.get("winner_song_id")
        winner = track_by_song.get(winner_song) if winner_song else None
        created_at = _parse_iso(entry.get("created_at"))
        key = (owner_config_id, sub_group, track_a.id, track_b.id, _iso(created_at))
        if key in seen:
            continue
        seen.add(key)
        comparison = CoverComparison(
            sub_group=sub_group,
            owner_config_id=owner_config_id,
            track_a_id=track_a.id,
            track_b_id=track_b.id,
            winner_track_id=winner.id if winner is not None else None,
            pct_a=entry.get("pct_a"),
            pct_b=entry.get("pct_b"),
        )
        if created_at is not None:
            comparison.created_at = created_at
        session.add(comparison)
        affected.add(sub_group)
    session.flush()
    return affected


def track_to_payload(track: Track, favourite: bool | None = None) -> dict[str, Any]:
    # ``favourite`` overrides the shared Track flag with the exporting profile's own tag; None
    # (legacy/local export) falls back to the shared column.
    return {
        "song_id": track.song_id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "has_lyrics": track.has_lyrics,
        "sub_group": track.sub_group,
        "is_original_rendition": track.is_original_rendition,
        "favourite": track.favourite if favourite is None else favourite,
        "manual_multiplier": track.manual_multiplier,
        "clip_start_seconds": track.clip_start_seconds,
        "clip_end_seconds": track.clip_end_seconds,
        "audio_only": track.audio_only,
        "assets": [
            {
                "file_path": asset.file_path,
                "asset_type": asset.asset_type,
                "codec": asset.codec,
                "container": asset.container,
                # URL-shaped sources are private provenance; never let them leave the local DB.
                "source": None
                if (asset.source or "").lower().startswith(("http://", "https://", "www."))
                else asset.source,
                "source_quality": asset.source_quality,
                "is_lossless": asset.is_lossless,
                "checksum": asset.checksum,
                "browser_supported": asset.browser_supported,
            }
            for asset in track.assets
        ],
        "embeds": [
            {
                "provider": embed.provider,
                "external_id": embed.external_id,
                "url": embed.url,
                "start_seconds": embed.start_seconds,
            }
            for embed in track.embeds
        ],
        "groups": [
            {
                "name": membership.group.name,
                "group_type": membership.group.group_type,
                "share": membership.share,
            }
            for membership in track.memberships
        ],
        "cooldown_tags": [link.tag.name for link in track.cooldown_tags],
        "ratings": {
            rating.factor.key: rating.value
            for rating in track.ratings
            if rating.factor is not None and rating.value is not None
        },
    }


def upsert_rating_factors(
    session: Session,
    payloads: list[dict[str, Any]],
) -> dict[str, RatingFactor]:
    factor_map = {factor.key: factor for factor in session.scalars(select(RatingFactor))}
    for payload in payloads:
        factor = factor_map.get(payload["key"])
        if factor is None:
            factor = RatingFactor(key=payload["key"], label=payload.get("label", payload["key"]))
            session.add(factor)
            session.flush()
            factor_map[factor.key] = factor
        factor.label = payload.get("label", factor.label)
        factor.weight = float(payload.get("weight", factor.weight))
        factor.applies_to_lyrics = bool(payload.get("applies_to_lyrics", factor.applies_to_lyrics))
        factor.applies_to_instrumental = bool(
            payload.get("applies_to_instrumental", factor.applies_to_instrumental)
        )
        factor.applies_to_variants_only = bool(
            payload.get("applies_to_variants_only", factor.applies_to_variants_only)
        )
        factor.enabled = bool(payload.get("enabled", factor.enabled))
    return factor_map


def upsert_groups(session: Session, payloads: list[dict[str, Any]]) -> dict[str, WeightGroup]:
    group_map = {group.name: group for group in session.scalars(select(WeightGroup))}
    for payload in payloads:
        group = group_map.get(payload["name"])
        if group is None:
            group = WeightGroup(name=payload["name"], group_type=payload.get("group_type", "other"))
            session.add(group)
            session.flush()
            group_map[group.name] = group
        group.group_type = payload.get("group_type", group.group_type)
        group.manual_multiplier = float(payload.get("manual_multiplier", group.manual_multiplier))
        group.rating_multiplier = float(payload.get("rating_multiplier", group.rating_multiplier))
    return group_map


def upsert_asset(session: Session, track: Track, payload: dict[str, Any]) -> MediaAsset:
    asset = session.scalar(select(MediaAsset).where(MediaAsset.file_path == payload["file_path"]))
    if asset is None:
        asset = MediaAsset(track=track, file_path=payload["file_path"])
        session.add(asset)
    asset.asset_type = payload.get("asset_type", asset.asset_type)
    asset.codec = payload.get("codec")
    asset.container = payload.get("container")
    asset.source = payload.get("source")
    asset.source_quality = payload.get("source_quality")
    asset.is_lossless = payload.get("is_lossless")
    asset.checksum = payload.get("checksum")
    asset.browser_supported = bool(payload.get("browser_supported", asset.browser_supported))
    return asset


def _upsert_embed(session: Session, track: Track, payload: dict[str, Any]) -> None:
    """Add an embed for a song from its payload (provider+id, or a bare url we parse). Idempotent on
    (track, provider, external_id). Skips anything we don't recognise as a known provider."""
    provider = payload.get("provider")
    external_id = payload.get("external_id")
    url = payload.get("url")
    start_seconds = payload.get("start_seconds")
    if not (provider and external_id):
        parsed = parse_embed_url(url) if url else None
        if parsed is None:
            return
        provider, external_id = parsed.provider, parsed.external_id
        if start_seconds is None:
            start_seconds = parsed.start_seconds
    existing = session.scalar(
        select(Embed).where(
            Embed.track_id == track.id,
            Embed.provider == provider,
            Embed.external_id == external_id,
        )
    )
    if existing is None:
        session.add(
            Embed(
                track=track,
                provider=provider,
                external_id=external_id,
                url=url,
                start_seconds=start_seconds,
            )
        )
    else:
        existing.url = url
        existing.start_seconds = start_seconds


def upsert_track_tag(session: Session, track: Track, tag_name: str) -> None:
    tag = session.scalar(select(CooldownTag).where(CooldownTag.name == tag_name))
    if tag is None:
        tag = CooldownTag(name=tag_name)
        session.add(tag)
        session.flush()
    link = session.scalar(
        select(TrackCooldownTag).where(
            TrackCooldownTag.track_id == track.id,
            TrackCooldownTag.tag_id == tag.id,
        )
    )
    if link is None:
        session.add(TrackCooldownTag(track=track, tag=tag))
