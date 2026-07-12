"""Unified tags: system tags (Favourite, Ignored), starter custom tags, per-profile and shared
assignments, tag-restricted queues, and the light zero-mean pacing layer."""

from __future__ import annotations

from sqlalchemy import delete, select

from harmonica.db import SessionLocal, engine, init_db
from harmonica.models import (
    DEFAULT_CUSTOM_TAG_NAMES,
    FAVOURITE_TAG_NAME,
    IGNORED_TAG_NAME,
    DeviceConfig,
    DeviceConfigTrack,
    Tag,
    Track,
    TrackTag,
    seed_and_backfill_tags,
    visible_tags_by_track,
)
from harmonica.security import hash_passphrase


def test_seed_creates_system_and_starter_tags() -> None:
    init_db()
    with SessionLocal() as session:
        by_name = {tag.name: tag for tag in session.scalars(select(Tag))}
    assert by_name[FAVOURITE_TAG_NAME].kind == "system"
    assert by_name[IGNORED_TAG_NAME].kind == "system"
    for name in DEFAULT_CUSTOM_TAG_NAMES:
        assert by_name[name].kind == "custom"
        assert by_name[name].shared is False
        assert by_name[name].affects_algorithm is False


def test_seed_is_idempotent_and_does_not_resurrect_deleted_defaults() -> None:
    init_db()
    with SessionLocal() as session:
        tag = session.scalar(select(Tag).where(Tag.name == "Party"))
        if tag is not None:
            session.delete(tag)
            session.commit()
    seed_and_backfill_tags(engine)
    with SessionLocal() as session:
        assert session.scalar(select(Tag).where(Tag.name == "Party")) is None


def test_backfill_copies_both_favourite_columns() -> None:
    init_db()
    with SessionLocal() as session:
        track = Track(song_id="tags_backfill_1", title="Backfill", favourite=True)
        session.add(track)
        config = DeviceConfig(name="tags-backfill", passphrase_hash=hash_passphrase("pw"))
        session.add(config)
        session.flush()
        session.add(
            DeviceConfigTrack(config_id=config.id, track_id=track.id, favourite=True)
        )
        # Force a re-run of the one-time pass by clearing the tags tables.
        session.execute(delete(TrackTag))
        session.execute(delete(Tag))
        session.commit()
        track_id, config_id = track.id, config.id
    seed_and_backfill_tags(engine)
    with SessionLocal() as session:
        local_tags = visible_tags_by_track(session, None)
        owned_tags = visible_tags_by_track(session, config_id)
    assert FAVOURITE_TAG_NAME in local_tags.get(track_id, [])
    assert FAVOURITE_TAG_NAME in owned_tags.get(track_id, [])
