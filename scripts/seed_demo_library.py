"""Seed a realistic demo library for Harmonica front-end development.

Generates browser-playable WAV tones plus a richly overlapping library that mimics
the user's real ~250-song batch: musicals and artists as weight groups, cross-cutting
theme groups, dub/cover families as subgroups, partial ratings (to exercise cold start),
and some visual tracks (to exercise visual priority).

Usage:
    uv run python scripts/seed_demo_library.py            # wipe + reseed
    uv run python scripts/seed_demo_library.py --keep     # only add if empty

Media is written under .harmonica/sample-media/ (gitignored). Re-running is deterministic.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import wave
from pathlib import Path
from random import Random

from sqlalchemy import delete, select

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
    RatingFactor,
    Track,
    TrackCooldownTag,
    TrackRating,
    WeightGroup,
)
from harmonica.scanner import slugify

RNG = Random(20260625)
SAMPLE_RATE = 8000

# --- Library definition --------------------------------------------------------------
# Each entry: title, source-group, [theme groups], sub_group (dub/cover family) or None,
# artist, has_lyrics, has_video, rating profile key.
# Rating profiles drive how much of the track is rated (cold-start realism).

THEME = "theme"
SOURCE = "source"
ARTIST = "artist"

# (title, source_group, themes, sub_group, artist, has_lyrics, has_video, rating)
LIBRARY: list[tuple] = [
    # --- The Ashen City (large source group, heavy theme overlap) ---
    ("Look Away", "The Ashen City", ["Justice", "Poverty"], None, None, True, False, "high"),
    ("Stars (English)", "The Ashen City", ["Justice", "Faith"], "stars", None, True, True, "high"),
    ("Stars (French)", "The Ashen City", ["Justice", "Faith"], "stars", None, True, False, "mid"),
    ("Stars (Instrumental)", "The Ashen City", ["Justice"], "stars", None, False, False, "none"),
    ("Do You Hear the City Wake", "The Ashen City", ["Revolution", "Justice"], None, None, True, True, "high"),  # noqa: E501
    ("I Dreamt the Rain", "The Ashen City", ["Heartbreak", "Poverty"], None, None, True, True, "high"),
    ("Alone at Dawn", "The Ashen City", ["Heartbreak", "Love"], None, None, True, False, "mid"),
    ("One More Dawn", "The Ashen City", ["Revolution", "Love"], None, None, True, True, "high"),
    ("Lead Him Home", "The Ashen City", ["Faith", "Love"], None, None, True, False, "mid"),
    ("Empty Rooms, Silent Halls", "The Ashen City", ["Death", "Revolution"], None, None, True, False, "none"),  # noqa: E501

    # --- Meridian ---
    ("Meridian Rising", "Meridian", ["Ambition", "Revolution"], None, None, True, True, "high"),
    ("My Mark", "Meridian", ["Ambition", "Revolution"], None, None, True, True, "high"),
    ("Hold the Line (Corvin)", "Meridian", ["Ambition", "Love"], "hold_the_line", None, True, False, "mid"),
    ("Hold the Line (Reprise)", "Meridian", ["Ambition"], "hold_the_line", None, True, False, "none"),
    ("The Severin Sisters", "Meridian", ["Love", "Revolution"], None, None, True, True, "mid"),
    ("Requited", "Meridian", ["Love", "Heartbreak"], None, None, True, False, "high"),
    ("It's Quiet Now", "Meridian", ["Death", "Love"], None, None, True, False, "none"),
    ("Behind Closed Doors", "Meridian", ["Ambition"], None, None, True, True, "mid"),

    # --- Undertide ---
    ("Follow Me Down", "Undertide", ["Love", "Myth"], "follow_me_down", None, True, True, "high"),
    ("Follow Me Down (Reprise)", "Undertide", ["Love", "Myth", "Death"], "follow_me_down", None, True, False, "none"),  # noqa: E501
    ("Way Down Undertide", "Undertide", ["Myth", "Poverty"], None, None, True, True, "mid"),
    ("Tidebound III", "Undertide", ["Love", "Myth"], None, None, True, False, "mid"),
    ("Why We Guard the Gate", "Undertide", ["Poverty", "Justice"], None, None, True, False, "none"),
    ("Flowers", "Undertide", ["Love", "Death"], None, None, True, False, "mid"),

    # --- Tidebound: The Musical ---
    ("The Ship and the Storm", "Tidebound: The Musical", ["War", "Myth"], None, None, True, True, "mid"),
    ("Open Water", "Tidebound: The Musical", ["Love", "Myth"], None, None, True, False, "mid"),
    ("Keeper of the Tide", "Tidebound: The Musical", ["War", "Ambition"], None, None, True, True, "high"),
    ("Cruelty", "Tidebound: The Musical", ["War", "Death"], None, None, True, False, "none"),
    ("Monster", "Tidebound: The Musical", ["War", "Myth"], None, None, True, False, "mid"),

    # --- Gilded Mask ---
    ("The Gilded Mask", "The Gilded Mask", ["Obsession", "Love"], None, None, True, True, "high"),  # noqa: E501
    ("The Hush of Midnight", "The Gilded Mask", ["Obsession", "Love"], None, None, True, False, "mid"),  # noqa: E501
    ("All I Could Ask", "The Gilded Mask", ["Love"], None, None, True, False, "mid"),
    ("Maskfall", "The Gilded Mask", ["Obsession"], None, None, True, True, "none"),

    # --- Rook Harrow (artist group) ---
    ("Take Me to Water", "Rook Harrow", ["Faith", "Love"], None, "Rook Harrow", True, True, "high"),
    ("Field Song", "Rook Harrow", ["Love"], None, "Rook Harrow", True, False, "mid"),
    ("Bramble Wine", "Rook Harrow", ["Love", "Heartbreak"], None, "Rook Harrow", True, False, "mid"),
    ("Evensong (Harrow)", "Rook Harrow", ["Faith", "Heartbreak"], "evensong", "Rook Harrow", True, False, "high"),  # noqa: E501
    ("Feed the Crows", "Rook Harrow", ["Justice"], None, "Rook Harrow", True, True, "none"),

    # --- Elm Casey ---
    ("Evensong (Casey)", "Elm Casey", ["Faith", "Melancholy"], "evensong", "Elm Casey", True, False, "mid"),  # noqa: E501
    ("Cipher of Love", "Elm Casey", ["Love", "Melancholy"], None, "Elm Casey", True, True, "high"),  # noqa: E501
    ("Ought to Have Known", "Elm Casey", ["Melancholy"], None, "Elm Casey", True, False, "mid"),  # noqa: E501
    ("Grief with Grace", "Elm Casey", ["Death", "Melancholy"], None, "Elm Casey", True, False, "none"),  # noqa: E501
    ("Visions of Arden", "Elm Casey", ["Love", "Melancholy"], None, "Elm Casey", True, False, "none"),  # noqa: E501

    # --- Vera Lane ---
    ("All Too Late", "Vera Lane", ["Heartbreak", "Love"], None, "Vera Lane", True, True, "high"),
    ("Overcoat", "Vera Lane", ["Love", "Melancholy"], None, "Vera Lane", True, False, "mid"),
    ("Counterlight", "Vera Lane", ["Melancholy"], None, "Vera Lane", True, True, "mid"),
    ("Glasshouse Problems", "Vera Lane", ["Heartbreak"], None, "Vera Lane", True, False, "high"),
    ("The Falconer", "Vera Lane", ["Love", "Heartbreak"], None, "Vera Lane", True, False, "none"),
    ("Late Summer", "Vera Lane", ["Love", "Melancholy"], None, "Vera Lane", True, False, "mid"),

    # --- Standalone covers / instrumental family (Evensong original) ---
    ("Evensong (Original)", "Standalone", ["Faith"], "evensong", "Abel Frost", True, False, "mid"),  # noqa: E501
    ("Nightwater", "Standalone", ["Melancholy"], None, "A. Vasel", False, False, "high"),
    ("Stillness No. 1", "Standalone", ["Melancholy"], None, "E. Norling", False, False, "mid"),
    ("Time", "Standalone", ["Melancholy", "Myth"], None, "Kade Winter", False, True, "high"),
]


def write_wav(path: Path, seconds: float, frequency: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(SAMPLE_RATE * seconds)
    fade = int(SAMPLE_RATE * 0.05)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        buffer = bytearray()
        for index in range(frames):
            envelope = 1.0
            if index < fade:
                envelope = index / fade
            elif index > frames - fade:
                envelope = max(0.0, (frames - index) / fade)
            sample = math.sin(2 * math.pi * frequency * (index / SAMPLE_RATE))
            value = int(sample * envelope * 9000)
            buffer += struct.pack("<h", value)
        handle.writeframes(bytes(buffer))


RATING_FACTORS = ["lyrics", "music", "performance", "inspiration", "focus", "overall"]


def ratings_for(profile: str, has_lyrics: bool, is_variant: bool) -> dict[str, float | None]:
    """Return per-factor star values honoring applicability and the coverage profile."""
    if profile == "none":
        return {}
    base = {"high": 4.0, "mid": 3.0, "low": 2.0}[profile]
    values: dict[str, float | None] = {}
    for factor in RATING_FACTORS:
        if factor == "lyrics" and not has_lyrics:
            continue
        if factor == "focus" and has_lyrics:
            continue  # focus applies mainly to instrumental tracks
        if factor == "performance" and not is_variant:
            continue  # performance applies mainly to variant/cover families
        jitter = RNG.choice([-1.0, 0.0, 0.0, 1.0])
        values[factor] = max(0.0, min(5.0, base + jitter))
    # Leave some "mid" tracks only partially rated to exercise partial coverage.
    if profile == "mid" and len(values) > 2 and RNG.random() < 0.4:
        drop = RNG.choice(list(values))
        values.pop(drop)
    return values


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


def variant_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in LIBRARY:
        sub_group = row[3]
        if sub_group:
            counts[sub_group] = counts.get(sub_group, 0) + 1
    return counts


def seed(keep: bool) -> None:
    settings = get_settings()
    init_db()
    media_root = settings.home / "sample-media"
    with SessionLocal() as session:
        ensure_default_rating_factors(session)
        existing = session.query(Track).count()
        if keep and existing > 1:
            print(f"Library already has {existing} tracks; --keep set, leaving it alone.")
            return
        reset_tables(session)
        ensure_default_rating_factors(session)

        factors = {f.key: f for f in session.scalars(select(RatingFactor))}
        groups: dict[str, WeightGroup] = {}

        def group(name: str, group_type: str) -> WeightGroup:
            if name not in groups:
                grp = WeightGroup(name=name, group_type=group_type)
                session.add(grp)
                session.flush()
                groups[name] = grp
            return groups[name]

        var_counts = variant_counts()
        for order, row in enumerate(LIBRARY):
            title, source, themes, sub_group, artist, has_lyrics, has_video, profile = row
            album = source if source != "Standalone" else None
            song_id = slugify(f"{source}_{title}") or f"track_{order}"
            track = Track(
                song_id=song_id,
                title=title,
                artist=artist or (source if source != "Standalone" else None),
                album=album,
                has_lyrics=has_lyrics,
                sub_group=sub_group,
            )
            session.add(track)
            session.flush()

            # Source group (musical) or artist group as the primary weight group.
            if source != "Standalone":
                session.add(GroupMembership(track=track, group=group(source, SOURCE), share=None))
            if artist and artist != source:
                session.add(GroupMembership(track=track, group=group(artist, ARTIST), share=None))
            for theme in themes:
                session.add(GroupMembership(track=track, group=group(theme, THEME), share=None))

            # Audio asset (always playable).
            duration = RNG.uniform(5.0, 14.0)
            frequency = 196.0 * (2 ** (RNG.randint(0, 18) / 12.0))  # spread across ~1.5 octaves
            audio_path = media_root / f"{song_id}.wav"
            write_wav(audio_path, duration, frequency)
            session.add(
                MediaAsset(
                    track=track,
                    file_path=str(audio_path),
                    asset_type="audio",
                    codec="pcm_s16le",
                    container="wav",
                    source="demo-seed",
                    source_quality="synthetic tone",
                    is_lossless=True,
                    browser_supported=True,
                )
            )
            # Visual tracks get a video asset row (metadata only for the synthetic set:
            # the queue plays the audio asset, but has_video/visual-priority is exercised).
            if has_video:
                session.add(
                    MediaAsset(
                        track=track,
                        file_path=str(media_root / f"{song_id}.mp4"),
                        asset_type="video",
                        codec="h264",
                        container="mp4",
                        source="demo-seed",
                        source_quality="720p (placeholder)",
                        is_lossless=False,
                        browser_supported=True,
                    )
                )

            is_variant = bool(sub_group and var_counts.get(sub_group, 1) > 1)
            for key, value in ratings_for(profile, has_lyrics, is_variant).items():
                factor = factors.get(key)
                if factor is not None:
                    session.add(TrackRating(track=track, factor=factor, value=value))

        session.commit()
        total = session.query(Track).count()
        assets = session.query(MediaAsset).count()
        grp_count = session.query(WeightGroup).count()
        print(f"Seeded {total} tracks, {assets} assets, {grp_count} groups under {media_root}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="Only seed if the library is empty.")
    args = parser.parse_args()
    seed(keep=args.keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
