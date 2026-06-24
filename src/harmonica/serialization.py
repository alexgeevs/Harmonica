from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from harmonica.models import (
    CooldownTag,
    GroupMembership,
    MediaAsset,
    RatingFactor,
    Track,
    TrackCooldownTag,
    TrackRating,
    WeightGroup,
)


def export_library(session: Session, output_path: Path) -> None:
    tracks = list(
        session.scalars(
            select(Track).options(
                selectinload(Track.assets),
                selectinload(Track.memberships).selectinload(GroupMembership.group),
                selectinload(Track.ratings).selectinload(TrackRating.factor),
                selectinload(Track.cooldown_tags).selectinload(TrackCooldownTag.tag),
            )
        )
    )
    groups = list(session.scalars(select(WeightGroup)))
    factors = list(session.scalars(select(RatingFactor)))
    payload = {
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
        "tracks": [track_to_payload(track) for track in tracks],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def import_library(session: Session, input_path: Path) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    factor_map = upsert_rating_factors(session, payload.get("rating_factors", []))
    group_map = upsert_groups(session, payload.get("groups", []))

    for track_payload in payload.get("tracks", []):
        track = session.scalar(select(Track).where(Track.song_id == track_payload["song_id"]))
        if track is None:
            track = Track(
                song_id=track_payload["song_id"],
                title=track_payload.get("title") or "Untitled",
            )
            session.add(track)
            session.flush()
        track.title = track_payload.get("title") or track.title
        track.artist = track_payload.get("artist")
        track.album = track_payload.get("album")
        track.has_lyrics = bool(track_payload.get("has_lyrics", True))
        track.sub_group = track_payload.get("sub_group")
        track.manual_multiplier = float(track_payload.get("manual_multiplier", 1.0))

        for asset_payload in track_payload.get("assets", []):
            upsert_asset(session, track, asset_payload)
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
            rating.value = value
    session.commit()


def track_to_payload(track: Track) -> dict[str, Any]:
    return {
        "song_id": track.song_id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "has_lyrics": track.has_lyrics,
        "sub_group": track.sub_group,
        "manual_multiplier": track.manual_multiplier,
        "assets": [
            {
                "file_path": asset.file_path,
                "asset_type": asset.asset_type,
                "codec": asset.codec,
                "container": asset.container,
                "source": asset.source,
                "source_quality": asset.source_quality,
                "is_lossless": asset.is_lossless,
                "checksum": asset.checksum,
                "browser_supported": asset.browser_supported,
            }
            for asset in track.assets
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
