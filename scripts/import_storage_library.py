"""Import the real downloaded library from Storage/ into Harmonica.

The Storage agent lays out one folder per song under Storage/songs/<id>_<title>/,
each with a song_config.json (title, artists, weight groups, version/variant family)
plus the downloaded media (.mp4 video and/or .m4a/.opus audio).

This maps that structure onto Harmonica:
    song_title_guess     -> Track.title
    original_artist_names -> Track.artist (first cleaned segment)
    weight_group_names   -> WeightGroup memberships (type "source")
    version_family_name  -> Track.sub_group  (dub/cover/variant family)
    *.mp4 / *.m4a / ...  -> MediaAsset rows (video / audio)

It wipes the existing library and rebuilds (safe before any real ratings exist).
Re-run it as more downloads land.

    uv run python scripts/import_storage_library.py [--storage PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete

from harmonica.bootstrap import ensure_default_rating_factors
from harmonica.config import get_settings
from harmonica.db import SessionLocal, init_db
from harmonica.models import (
    CooldownTag,
    GroupMembership,
    MediaAsset,
    PlaybackEvent,
    PlaylistItem,
    PlaylistRun,
    Track,
    TrackCooldownTag,
    TrackRating,
    WeightGroup,
)

AUDIO_EXTS = {".m4a", ".opus", ".mp3", ".ogg", ".wav", ".flac", ".aac"}
VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".m4v"}
BROWSER_OK = {".mp4", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm", ".flac"}
LOSSLESS = {".wav", ".flac", ".aiff", ".alac"}
INCOMPLETE = {".part", ".dashvideo", ".dashaudio", ".ytdl", ".tmp"}


def clean_artist(raw: str | None) -> str | None:
    if not raw:
        return None
    first = raw.split(";")[0].strip().strip('"').strip("/").strip()
    return first or None


def split_groups(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.replace("/", ";").split(";"):
        name = chunk.strip().strip('"').strip()
        if name and name.lower() not in {"unknown", "review", "unknown / review"}:
            parts.append(name)
    # De-dup, preserve order.
    seen: set[str] = set()
    unique: list[str] = []
    for name in parts:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def media_files(song_dir: Path) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in sorted(song_dir.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in INCOMPLETE:
            continue
        if ext in VIDEO_EXTS:
            found.append((path, "video"))
        elif ext in AUDIO_EXTS:
            found.append((path, "audio"))
    return found


def reset_tables(session) -> None:
    for model in (
        PlaybackEvent,
        PlaylistItem,
        PlaylistRun,
        TrackRating,
        TrackCooldownTag,
        GroupMembership,
        MediaAsset,
        CooldownTag,
        WeightGroup,
        Track,
    ):
        session.execute(delete(model))
    session.commit()


def import_library(storage: Path) -> None:
    songs_root = storage / "songs"
    if not songs_root.is_dir():
        raise SystemExit(f"No songs directory at {songs_root}")

    init_db()
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
        reset_tables(session)

        groups: dict[str, WeightGroup] = {}

        def group(name: str) -> WeightGroup:
            if name not in groups:
                grp = WeightGroup(name=name, group_type="source")
                session.add(grp)
                session.flush()
                groups[name] = grp
            return groups[name]

        tracks = 0
        assets = 0
        without_media = 0
        with_video = 0
        for song_dir in sorted(songs_root.iterdir()):
            config_path = song_dir / "song_config.json"
            if not config_path.is_file():
                continue
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            track_id = config.get("track_id") or song_dir.name
            title = (config.get("song_title_guess") or config.get("original_title") or song_dir.name).strip()
            artist = clean_artist(config.get("original_artist_names"))
            group_names = split_groups(config.get("weight_group_names"))
            sub_group = (config.get("version_family_name") or None) or None
            album = group_names[0] if group_names else None

            track = Track(
                song_id=str(track_id),
                title=title[:255],
                artist=artist[:255] if artist else None,
                album=album[:255] if album else None,
                has_lyrics=True,
                sub_group=sub_group[:255] if sub_group else None,
            )
            session.add(track)
            session.flush()
            tracks += 1

            for name in group_names:
                session.add(GroupMembership(track=track, group=group(name[:255]), share=None))

            files = media_files(song_dir)
            if not files:
                without_media += 1
            has_video = False
            for path, kind in files:
                ext = path.suffix.lower()
                if kind == "video":
                    has_video = True
                session.add(
                    MediaAsset(
                        track=track,
                        file_path=str(path),
                        asset_type=kind,
                        codec=None,
                        container=ext.lstrip("."),
                        source=config.get("url"),
                        source_quality=config.get("version_type"),
                        is_lossless=ext in LOSSLESS,
                        browser_supported=ext in BROWSER_OK,
                    )
                )
                assets += 1
            if has_video:
                with_video += 1

        session.commit()
        print(
            f"Imported {tracks} tracks, {assets} assets, {len(groups)} groups "
            f"({with_video} with video, {without_media} still without media)."
        )


def main() -> int:
    settings = get_settings()
    default_storage = Path(__file__).resolve().parent.parent / "Storage"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=default_storage)
    args = parser.parse_args()
    print(f"Harmonica home: {settings.home}")
    import_library(args.storage.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
