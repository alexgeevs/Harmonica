from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from harmonica.models import GroupMembership, MediaAsset, Track, WeightGroup

AUDIO_EXTENSIONS = {".aac", ".aiff", ".alac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
VIDEO_EXTENSIONS = {".m4v", ".mkv", ".mov", ".mp4", ".webm"}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
BROWSER_SUPPORTED_EXTENSIONS = {".flac", ".m4a", ".mp3", ".mp4", ".ogg", ".opus", ".wav", ".webm"}
LOSSLESS_EXTENSIONS = {".aiff", ".alac", ".flac", ".wav"}


@dataclass
class ScanResult:
    scanned: int = 0
    created_tracks: int = 0
    created_assets: int = 0
    skipped_existing_assets: int = 0


def scan_library(session: Session, root: Path, create_tag_groups: bool = True) -> ScanResult:
    root = root.expanduser().resolve()
    result = ScanResult()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
            continue
        result.scanned += 1
        existing_asset = session.scalar(select(MediaAsset).where(MediaAsset.file_path == str(path)))
        if existing_asset:
            result.skipped_existing_assets += 1
            continue
        tags = read_tags(path)
        checksum = sha256_file(path)
        track, created_track = find_or_create_track(session, path, tags, checksum)
        if created_track:
            result.created_tracks += 1
        asset = MediaAsset(
            track=track,
            file_path=str(path),
            asset_type="video" if path.suffix.lower() in VIDEO_EXTENSIONS else "audio",
            codec=tags.get("codec"),
            container=path.suffix.lower().lstrip("."),
            source=tags.get("source"),
            source_quality=tags.get("source_quality"),
            is_lossless=path.suffix.lower() in LOSSLESS_EXTENSIONS,
            checksum=checksum,
            browser_supported=path.suffix.lower() in BROWSER_SUPPORTED_EXTENSIONS,
        )
        session.add(asset)
        result.created_assets += 1
        if create_tag_groups:
            ensure_initial_groups(session, track, tags)
    session.commit()
    return result


def read_tags(path: Path) -> dict[str, str | None]:
    tags: dict[str, str | None] = {
        "title": None,
        "artist": None,
        "album": None,
        "codec": None,
        "source": None,
        "source_quality": None,
    }
    try:
        media = MutagenFile(path, easy=True)
    except Exception:
        media = None
    if media is None:
        tags["title"] = path.stem
        return tags

    raw_tags: dict[str, Any] = media.tags or {}
    tags["title"] = first_tag(raw_tags, "title") or path.stem
    tags["artist"] = first_tag(raw_tags, "artist", "albumartist", "composer")
    tags["album"] = first_tag(raw_tags, "album")
    tags["source"] = first_tag(raw_tags, "source", "website", "organization")
    tags["source_quality"] = first_tag(raw_tags, "comment", "description")
    mime = getattr(media.info, "mime", None)
    if mime:
        tags["codec"] = ",".join(mime) if isinstance(mime, list) else str(mime)
    else:
        tags["codec"] = path.suffix.lower().lstrip(".")
    return tags


def first_tag(raw_tags: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = raw_tags.get(key)
        if isinstance(value, list) and value:
            return str(value[0])
        if value:
            return str(value)
    return None


def find_or_create_track(
    session: Session,
    path: Path,
    tags: dict[str, str | None],
    checksum: str,
) -> tuple[Track, bool]:
    title = tags.get("title") or path.stem
    artist = tags.get("artist")
    album = tags.get("album")
    base_song_id = slugify("_".join(part for part in [artist, album, title] if part))
    song_id = f"{base_song_id}_{checksum[:8]}" if base_song_id else f"track_{checksum[:12]}"
    existing = session.scalar(select(Track).where(Track.song_id == song_id))
    if existing:
        return existing, False
    track = Track(song_id=song_id, title=title, artist=artist, album=album)
    session.add(track)
    session.flush()
    return track, True


def ensure_initial_groups(session: Session, track: Track, tags: dict[str, str | None]) -> None:
    candidates: list[tuple[str, str]] = []
    if tags.get("album"):
        candidates.append((tags["album"] or "", "source"))
    if tags.get("artist"):
        candidates.append((tags["artist"] or "", "artist"))
    if not candidates:
        candidates.append(("Standalone", "other"))

    for name, group_type in candidates:
        group = session.scalar(select(WeightGroup).where(WeightGroup.name == name))
        if group is None:
            group = WeightGroup(name=name, group_type=group_type)
            session.add(group)
            session.flush()
        membership = session.scalar(
            select(GroupMembership).where(
                GroupMembership.track_id == track.id,
                GroupMembership.group_id == group.id,
            )
        )
        if membership is None:
            session.add(GroupMembership(track=track, group=group, share=None))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    replaced = re.sub(r"[^a-z0-9]+", "_", lowered)
    return re.sub(r"_+", "_", replaced).strip("_")
