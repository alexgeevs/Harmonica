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

By default it **upserts by song_id**: new songs are added and each song's media
files are reconciled (new files linked, re-encoded/removed files dropped), while all
per-song curation — trim points, audio-only, ratings, group edits, manual weights —
is preserved. Re-run it freely as downloads land or songs are re-encoded.

    uv run python scripts/import_storage_library.py [--storage PATH]
    uv run python scripts/import_storage_library.py --reset   # full rebuild (discards curation)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, select

from harmonica.bootstrap import ensure_default_rating_factors
from harmonica.config import get_settings
from harmonica.db import SessionLocal, engine, init_db
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
    ensure_additive_track_columns,
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


def reconcile_assets(session, track: Track, song_dir: Path, config: dict) -> tuple[int, int, bool]:
    """Link new media files and drop assets whose file is gone (e.g. re-encoded)."""
    files = media_files(song_dir)
    current = {str(path): kind for path, kind in files}
    existing = {asset.file_path: asset for asset in track.assets}

    removed = 0
    for path, asset in existing.items():
        if path not in current:
            session.delete(asset)
            removed += 1

    added = 0
    for path, kind in current.items():
        if path in existing:
            continue
        if session.scalar(select(MediaAsset).where(MediaAsset.file_path == path)) is not None:
            continue
        ext = Path(path).suffix.lower()
        session.add(
            MediaAsset(
                track=track,
                file_path=path,
                asset_type=kind,
                codec=None,
                container=ext.lstrip("."),
                source=config.get("url"),
                source_quality=config.get("version_type"),
                is_lossless=ext in LOSSLESS,
                browser_supported=ext in BROWSER_OK,
            )
        )
        added += 1

    has_video = any(kind == "video" for kind in current.values())
    return added, removed, has_video


def import_library(storage: Path, reset: bool = False) -> None:
    """Upsert the Storage library by song_id.

    Existing tracks keep all user-curated data (trim points, audio-only, ratings,
    group edits, manual weights); only their media files are reconciled. New songs
    are created from the source config. Pass reset=True for a full rebuild.
    """
    songs_root = storage / "songs"
    if not songs_root.is_dir():
        raise SystemExit(f"No songs directory at {songs_root}")

    init_db()
    ensure_additive_track_columns(engine)
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
        if reset:
            reset_tables(session)

        groups: dict[str, WeightGroup] = {
            grp.name: grp for grp in session.scalars(select(WeightGroup))
        }

        def group(name: str) -> WeightGroup:
            if name not in groups:
                grp = WeightGroup(name=name, group_type="source")
                session.add(grp)
                session.flush()
                groups[name] = grp
            return groups[name]

        new_tracks = 0
        kept_tracks = 0
        assets_added = 0
        assets_removed = 0
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

            track_id = str(config.get("track_id") or song_dir.name)
            track = session.scalar(select(Track).where(Track.song_id == track_id))
            if track is None:
                # New song: seed metadata + groups from the source config.
                title = (
                    config.get("song_title_guess") or config.get("original_title") or song_dir.name
                ).strip()
                artist = clean_artist(config.get("original_artist_names"))
                group_names = split_groups(config.get("weight_group_names"))
                sub_group = config.get("version_family_name") or None
                album = group_names[0] if group_names else None
                track = Track(
                    song_id=track_id,
                    title=title[:255],
                    artist=artist[:255] if artist else None,
                    album=album[:255] if album else None,
                    has_lyrics=True,
                    sub_group=sub_group[:255] if sub_group else None,
                )
                session.add(track)
                session.flush()
                for name in group_names:
                    session.add(GroupMembership(track=track, group=group(name[:255]), share=None))
                new_tracks += 1
            else:
                # Existing song: preserve all curation, only refresh media below.
                kept_tracks += 1

            added, removed, has_video = reconcile_assets(session, track, song_dir, config)
            assets_added += added
            assets_removed += removed
            if not media_files(song_dir):
                without_media += 1
            if has_video:
                with_video += 1

        session.commit()
        mode = "reset" if reset else "upsert"
        print(
            f"Import ({mode}): {new_tracks} new, {kept_tracks} preserved; "
            f"+{assets_added}/-{assets_removed} assets; "
            f"{with_video} with video, {without_media} without media."
        )


def main() -> int:
    settings = get_settings()
    default_storage = Path(__file__).resolve().parent.parent / "Storage"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=default_storage)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe and rebuild from scratch (DISCARDS trim/audio-only/ratings/group edits).",
    )
    args = parser.parse_args()
    print(f"Harmonica home: {settings.home}")
    import_library(args.storage.resolve(), reset=args.reset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
