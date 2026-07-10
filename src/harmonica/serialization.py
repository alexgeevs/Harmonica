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
from harmonica.embeds import is_valid_external_id, parse_embed_url
from harmonica.models import (
    CooldownTag,
    CoverComparison,
    DeviceConfig,
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
from harmonica.settings_store import (
    SETTING_MAP,
    get_setting_values,
    sanitize_value,
    update_setting_values,
)

EXPORT_SCOPES = ("all", "metadata", "ratings", "settings")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
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


def _dict_list(value: Any) -> list[dict[str, Any]]:
    """A hostile or corrupted file may put anything where a list of objects belongs;
    only the dict entries survive, everything else is dropped rather than crashing."""
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _text(value: Any, default: str | None = None, max_len: int = 1000) -> str | None:
    """Accept only real, non-empty strings from an import; length-capped so one field
    cannot balloon the database."""
    if not isinstance(value, str):
        return default
    trimmed = value.strip()
    if not trimmed:
        return default
    return trimmed[:max_len]


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    result = _finite(value, math.nan)
    return None if math.isnan(result) else result


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def export_library(session: Session, output_path: Path) -> None:
    payload = export_library_payload(session)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_library_payload(
    session: Session,
    owner_config_id: int | None = None,
    scope: str = "all",
) -> dict[str, Any]:
    """Build the export payload. ``scope`` limits it to one concern so a user can
    take just their song list, just their opinions, or just their dials:

    - ``metadata``: groups and tracks (files, embeds, groups, tags), without ratings.
    - ``ratings``: rating factors, per-song current stars, and the raw rating/cover
      history the algorithm derives from.
    - ``settings``: the adjustable controls, by key. Never the server's host/port,
      paths, or any credentials — those live outside the exportable settings store.
    - ``all``: everything above in one file.
    """
    if scope not in EXPORT_SCOPES:
        raise ValueError(f"Unknown export scope: {scope}")
    with_metadata = scope in ("all", "metadata")
    with_ratings = scope in ("all", "ratings")
    with_settings = scope in ("all", "settings")
    payload: dict[str, Any] = {
        "format": "harmonica-library",
        "version": 1,
        "scope": scope,
    }
    tracks: list[Track] = []
    if with_metadata or with_ratings:
        track_select = select(Track).options(
            selectinload(Track.assets),
            selectinload(Track.embeds),
            selectinload(Track.memberships).selectinload(GroupMembership.group),
            selectinload(Track.ratings).selectinload(TrackRating.factor),
            selectinload(Track.cooldown_tags).selectinload(TrackCooldownTag.tag),
        )
        if owner_config_id is not None:
            # An owned export carries only that profile's own library (privacy: never another
            # user's).
            track_select = track_select.join(
                DeviceConfigTrack, DeviceConfigTrack.track_id == Track.id
            ).where(DeviceConfigTrack.config_id == owner_config_id)
        tracks = list(session.scalars(track_select))
    if with_ratings:
        payload["rating_factors"] = [
            {
                "key": factor.key,
                "label": factor.label,
                "weight": factor.weight,
                "applies_to_lyrics": factor.applies_to_lyrics,
                "applies_to_instrumental": factor.applies_to_instrumental,
                "applies_to_variants_only": factor.applies_to_variants_only,
                "enabled": factor.enabled,
            }
            for factor in session.scalars(select(RatingFactor))
        ]
    if with_metadata:
        # Favourites are per-profile: an owned export carries the exporting profile's own tags.
        owner_favourites = (
            favourite_track_ids(session, owner_config_id) if owner_config_id is not None else None
        )
        payload["groups"] = [
            {
                "name": group.name,
                "group_type": group.group_type,
                "manual_multiplier": group.manual_multiplier,
                "rating_multiplier": group.rating_multiplier,
            }
            for group in session.scalars(select(WeightGroup))
        ]
        payload["tracks"] = [
            track_to_payload(
                track,
                favourite=(track.id in owner_favourites)
                if owner_favourites is not None
                else None,
                include_ratings=with_ratings,
            )
            for track in tracks
        ]
    if with_ratings:
        # Raw, append-only history the algorithm derives from. Keyed by song_id/factor_key so it
        # survives a move to another device (where local row ids differ). Device-local session/run
        # ids are stripped — they have no meaning on the destination.
        payload["rating_samples"] = rating_samples_payload(
            session, owner_config_id=owner_config_id
        )
        payload["cover_comparisons"] = cover_comparisons_payload(
            session, owner_config_id=owner_config_id
        )
        if not with_metadata and owner_config_id is None:
            # A ratings-only export still has to carry the current stars, which otherwise ride
            # on the track payloads. Only the legacy/local path needs this cache; a profile's
            # current ratings are always derived from its rating_samples.
            payload["track_ratings"] = [
                {
                    "song_id": track.song_id,
                    "ratings": {
                        rating.factor.key: rating.value
                        for rating in track.ratings
                        if rating.factor is not None and rating.value is not None
                    },
                }
                for track in tracks
                if any(
                    rating.factor is not None and rating.value is not None
                    for rating in track.ratings
                )
            ]
    if with_settings:
        payload["settings"] = _settings_export(session, owner_config_id)
    return payload


def _settings_export(session: Session, owner_config_id: int | None) -> dict[str, Any]:
    """The user-adjustable controls only. For a profile, its own snapshot overlays the
    shared values, matching what that profile actually plays with."""
    values = get_setting_values(session, get_settings())
    if owner_config_id is not None:
        config = session.get(DeviceConfig, owner_config_id)
        if config is not None:
            snapshot = json.loads(config.settings_json or "{}")
            values.update({key: snapshot[key] for key in snapshot if key in SETTING_MAP})
    return values


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
    import_library_payload(session, payload if isinstance(payload, dict) else {})


def _find_existing_track(
    session: Session, song_id: str, track_payload: dict[str, Any]
) -> Track | None:
    """Resolve an incoming track to one already in the shared pool: by ``song_id``, then by any
    asset ``checksum`` (same file content), then by ``file_path``. Enables dedupe-and-redirect so a
    second user importing the same song reuses the existing track/file."""
    track = session.scalar(select(Track).where(Track.song_id == song_id))
    if track is not None:
        return track
    for asset in _dict_list(track_payload.get("assets")):
        checksum = _text(asset.get("checksum"))
        if checksum:
            existing = session.scalar(select(MediaAsset).where(MediaAsset.checksum == checksum))
            if existing is not None:
                return existing.track
        file_path = _text(asset.get("file_path"), max_len=4000)
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
) -> dict[str, Any]:
    """Apply an exported payload (any scope) and return a summary of what landed.

    The payload is untrusted — it may come from a file a user was handed. Nothing in it is
    ever executed or trusted structurally: wrong-typed sections and entries are skipped,
    strings are length-capped, numbers cleaned of NaN/inf, ratings clamped to [0, 5] and
    settings to each control's own range. A crafted ``file_path`` can be stored but never
    served: /media confines serving to the media root (api.stream_media)."""
    factor_map = upsert_rating_factors(session, _dict_list(payload.get("rating_factors")))
    group_map = upsert_groups(session, _dict_list(payload.get("groups")))
    summary = {
        "tracks_created": 0,
        "tracks_matched": 0,
        "tracks_skipped": 0,
        "rating_samples_added": 0,
        "cover_comparisons_added": 0,
        "track_ratings_applied": 0,
        "settings_applied": 0,
    }

    for track_payload in _dict_list(payload.get("tracks")):
        song_id = _text(track_payload.get("song_id"), max_len=500)
        if song_id is None:
            summary["tracks_skipped"] += 1
            continue
        track = _find_existing_track(session, song_id, track_payload)
        is_new = track is None
        if is_new:
            track = Track(
                song_id=song_id,
                title=_text(track_payload.get("title"), "Untitled"),
            )
            session.add(track)
            session.flush()
            summary["tracks_created"] += 1
        else:
            summary["tracks_matched"] += 1

        # Shared content (metadata, assets, groups, tags) is written only when this import is
        # CREATING the track, or when it's a legacy/local (no-owner) import. An owned import that
        # matched an existing shared track just links to it — never overwriting another user's data.
        if is_new or owner_config_id is None:
            track.title = _text(track_payload.get("title"), track.title)
            track.artist = _text(track_payload.get("artist"))
            track.album = _text(track_payload.get("album"))
            track.has_lyrics = bool(track_payload.get("has_lyrics", True))
            track.sub_group = _text(track_payload.get("sub_group"))
            track.manual_multiplier = _finite(track_payload.get("manual_multiplier", 1.0), 1.0)
            if "is_original_rendition" in track_payload:
                track.is_original_rendition = bool(track_payload.get("is_original_rendition"))
            if "clip_start_seconds" in track_payload:
                track.clip_start_seconds = _finite_or_none(
                    track_payload.get("clip_start_seconds")
                )
            if "clip_end_seconds" in track_payload:
                track.clip_end_seconds = _finite_or_none(track_payload.get("clip_end_seconds"))
            if "audio_only" in track_payload:
                track.audio_only = bool(track_payload.get("audio_only"))

            for asset_payload in _dict_list(track_payload.get("assets")):
                upsert_asset(session, track, asset_payload)
            for embed_payload in _dict_list(track_payload.get("embeds")):
                _upsert_embed(session, track, embed_payload)
            for membership_payload in _dict_list(track_payload.get("groups")):
                group_name = _text(membership_payload.get("name"), max_len=300)
                if group_name is None:
                    continue
                group = group_map.get(group_name)
                if group is None:
                    group = WeightGroup(
                        name=group_name,
                        group_type=_text(membership_payload.get("group_type"), "other", 50),
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
                membership.share = _finite_or_none(membership_payload.get("share"))
            raw_tags = track_payload.get("cooldown_tags")
            for tag_name in raw_tags if isinstance(raw_tags, list) else []:
                cleaned_tag = _text(tag_name, max_len=300)
                if cleaned_tag is not None:
                    upsert_track_tag(session, track, cleaned_tag)

        # The shared latest-star cache is legacy-only; an owned profile's ratings ride in
        # rating_samples (owner-stamped below), never in the shared TrackRating rows.
        if owner_config_id is None:
            ratings_map = track_payload.get("ratings")
            for rating_key, value in (
                ratings_map.items() if isinstance(ratings_map, dict) else []
            ):
                factor = factor_map.get(rating_key)
                if factor is None:
                    continue
                _set_star_cache(session, track, factor, value)

        # Favourite is a per-user opinion: for a legacy import it rides on the shared Track; for an
        # owned import it stamps the profile's private link (never the shared column).
        fav_value = (
            bool(track_payload["favourite"]) if "favourite" in track_payload else None
        )
        if owner_config_id is None and fav_value is not None:
            track.favourite = fav_value
        _link_owner(session, owner_config_id, track.id, favourite=fav_value)
    session.flush()

    # Current stars from a ratings-only export (no track payloads to ride on). Legacy-only by
    # design: a profile's current ratings derive from its imported rating_samples instead.
    if owner_config_id is None:
        track_ratings = _dict_list(payload.get("track_ratings"))
        if track_ratings:
            track_by_song = {track.song_id: track for track in session.scalars(select(Track))}
            for entry in track_ratings:
                track = track_by_song.get(entry.get("song_id"))
                ratings_map = entry.get("ratings")
                if track is None or not isinstance(ratings_map, dict):
                    continue
                for rating_key, value in ratings_map.items():
                    factor = factor_map.get(rating_key)
                    if factor is None:
                        continue
                    _set_star_cache(session, track, factor, value)
                    summary["track_ratings_applied"] += 1

    summary["rating_samples_added"] = import_rating_samples(
        session, _dict_list(payload.get("rating_samples")), factor_map,
        owner_config_id=owner_config_id,
    )
    added_comparisons, affected_sets = import_cover_comparisons(
        session, _dict_list(payload.get("cover_comparisons")), owner_config_id=owner_config_id
    )
    summary["cover_comparisons_added"] = added_comparisons
    # Caches (Bradley-Terry strengths / set phase) are NEVER trusted from an export — they're
    # recomputed from the raw verdicts we just imported, so they're always self-consistent here.
    resolved_settings = settings or get_settings()
    for sub_group in affected_sets:
        recompute_set(session, sub_group, resolved_settings, owner_config_id=owner_config_id)

    raw_settings = payload.get("settings")
    if isinstance(raw_settings, dict):
        summary["settings_applied"] = _apply_imported_settings(
            session, raw_settings, resolved_settings, owner_config_id
        )
    session.commit()
    return summary


def _set_star_cache(session: Session, track: Track, factor: RatingFactor, value: Any) -> None:
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


def _apply_imported_settings(
    session: Session,
    raw: dict[str, Any],
    base_settings: Settings,
    owner_config_id: int | None,
) -> int:
    """Apply a settings section. Only known control keys land, each clamped to its own
    range by the same sanitiser the Settings screen uses — a file cannot set anything a
    user could not set by hand (and never host, port, paths, or credentials). A profile's
    import writes its own snapshot, never the shared values."""
    clean: dict[str, Any] = {}
    for key, value in raw.items():
        definition = SETTING_MAP.get(key)
        if definition is None:
            continue
        try:
            clean[key] = sanitize_value(definition, value)
        except (TypeError, ValueError):
            continue
    if not clean:
        return 0
    if owner_config_id is None:
        update_setting_values(session, clean, base_settings)
    else:
        config = session.get(DeviceConfig, owner_config_id)
        if config is None:
            return 0
        snapshot = json.loads(config.settings_json or "{}")
        snapshot.update(clean)
        config.settings_json = json.dumps(snapshot)
    return len(clean)


def import_rating_samples(
    session: Session,
    payloads: list[dict[str, Any]],
    factor_map: dict[str, RatingFactor],
    owner_config_id: int | None = None,
) -> int:
    track_by_song = {track.song_id: track for track in session.scalars(select(Track))}
    # The owner is part of the idempotency key, so re-importing under one profile won't duplicate,
    # yet two different profiles can each hold their own copy of the same history.
    seen = {
        (row.owner_config_id, row.track_id, row.factor_id, row.value, _iso(row.created_at))
        for row in session.scalars(select(RatingSample))
    }
    added = 0
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
            source=_text(entry.get("source"), "import", 100),
            owner_config_id=owner_config_id,
        )
        if created_at is not None:
            sample.created_at = created_at
        session.add(sample)
        added += 1
    return added


def import_cover_comparisons(
    session: Session,
    payloads: list[dict[str, Any]],
    owner_config_id: int | None = None,
) -> tuple[int, set[str]]:
    track_by_song = {track.song_id: track for track in session.scalars(select(Track))}
    seen = {
        (row.owner_config_id, row.sub_group, row.track_a_id, row.track_b_id, _iso(row.created_at))
        for row in session.scalars(select(CoverComparison))
    }
    added = 0
    affected: set[str] = set()
    for entry in payloads:
        track_a = track_by_song.get(entry.get("song_id_a"))
        track_b = track_by_song.get(entry.get("song_id_b"))
        sub_group = _text(entry.get("sub_group"), max_len=300)
        if track_a is None or track_b is None or sub_group is None:
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
            pct_a=_finite_or_none(entry.get("pct_a")),
            pct_b=_finite_or_none(entry.get("pct_b")),
        )
        if created_at is not None:
            comparison.created_at = created_at
        session.add(comparison)
        added += 1
        affected.add(sub_group)
    session.flush()
    return added, affected


def track_to_payload(
    track: Track, favourite: bool | None = None, include_ratings: bool = True
) -> dict[str, Any]:
    # ``favourite`` overrides the shared Track flag with the exporting profile's own tag; None
    # (legacy/local export) falls back to the shared column. ``include_ratings=False`` is the
    # metadata-only export: the song list without any opinions attached.
    payload = {
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
    }
    if include_ratings:
        payload["ratings"] = {
            rating.factor.key: rating.value
            for rating in track.ratings
            if rating.factor is not None and rating.value is not None
        }
    return payload


def upsert_rating_factors(
    session: Session,
    payloads: list[dict[str, Any]],
) -> dict[str, RatingFactor]:
    factor_map = {factor.key: factor for factor in session.scalars(select(RatingFactor))}
    for payload in payloads:
        key = _text(payload.get("key"), max_len=200)
        if key is None:
            continue
        factor = factor_map.get(key)
        if factor is None:
            factor = RatingFactor(key=key, label=_text(payload.get("label"), key, 300))
            session.add(factor)
            session.flush()
            factor_map[factor.key] = factor
        factor.label = _text(payload.get("label"), factor.label, 300)
        factor.weight = _finite(payload.get("weight", factor.weight), factor.weight)
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
        name = _text(payload.get("name"), max_len=300)
        if name is None:
            continue
        group = group_map.get(name)
        if group is None:
            group = WeightGroup(name=name, group_type=_text(payload.get("group_type"), "other", 50))
            session.add(group)
            session.flush()
            group_map[group.name] = group
        group.group_type = _text(payload.get("group_type"), group.group_type, 50)
        group.manual_multiplier = _finite(
            payload.get("manual_multiplier", group.manual_multiplier), group.manual_multiplier
        )
        group.rating_multiplier = _finite(
            payload.get("rating_multiplier", group.rating_multiplier), group.rating_multiplier
        )
    return group_map


def upsert_asset(session: Session, track: Track, payload: dict[str, Any]) -> MediaAsset | None:
    # The path is stored as data only; serving it stays confined to the media root
    # (api.stream_media), so a crafted path cannot expose files outside the library.
    file_path = _text(payload.get("file_path"), max_len=4000)
    if file_path is None:
        return None
    asset = session.scalar(select(MediaAsset).where(MediaAsset.file_path == file_path))
    if asset is None:
        asset = MediaAsset(track=track, file_path=file_path)
        session.add(asset)
    asset.asset_type = _text(payload.get("asset_type"), asset.asset_type, 50)
    asset.codec = _text(payload.get("codec"), max_len=100)
    asset.container = _text(payload.get("container"), max_len=100)
    asset.source = _text(payload.get("source"), max_len=300)
    asset.source_quality = _text(payload.get("source_quality"), max_len=100)
    asset.is_lossless = _bool_or_none(payload.get("is_lossless"))
    asset.checksum = _text(payload.get("checksum"), max_len=200)
    asset.browser_supported = bool(payload.get("browser_supported", asset.browser_supported))
    return asset


def _upsert_embed(session: Session, track: Track, payload: dict[str, Any]) -> None:
    """Add an embed for a song from its payload (provider+id, or a bare url we parse). Idempotent on
    (track, provider, external_id). Skips anything we don't recognise as a known provider."""
    provider = _text(payload.get("provider"), max_len=50)
    external_id = _text(payload.get("external_id"), max_len=100)
    url = _text(payload.get("url"), max_len=1000)
    start_seconds = _finite_or_none(payload.get("start_seconds"))
    # A directly-supplied provider+id must be well-formed for that provider; otherwise fall back to
    # parsing the URL, so an import can't store an arbitrary id that later reaches a player.
    if not (provider and external_id and is_valid_external_id(provider, external_id)):
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
