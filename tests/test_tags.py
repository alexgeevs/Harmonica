"""Unified tags: system tags (Favourite, Ignored), starter custom tags, per-profile and shared
assignments, tag-restricted queues, and the light zero-mean pacing layer."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from harmonica.api import create_app
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


def test_tag_crud_and_system_protection() -> None:
    with TestClient(create_app()) as client:
        listed = client.get("/tags").json()
        names = {entry["name"] for entry in listed}
        assert {FAVOURITE_TAG_NAME, IGNORED_TAG_NAME, "Fun", "Focused"} <= names

        created = client.post(
            "/tags", json={"name": "Workout", "shared": False, "affects_algorithm": True}
        )
        assert created.status_code == 200
        tag = created.json()
        assert tag["kind"] == "custom" and tag["affects_algorithm"] is True

        assert client.post("/tags", json={"name": "Workout"}).status_code == 409

        renamed = client.patch(f"/tags/{tag['id']}", json={"name": "Gym", "shared": True})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Gym" and renamed.json()["shared"] is True

        assert client.delete(f"/tags/{tag['id']}").status_code == 204
        assert "Gym" not in {entry["name"] for entry in client.get("/tags").json()}

        system_id = next(
            entry["id"] for entry in listed if entry["name"] == FAVOURITE_TAG_NAME
        )
        assert client.patch(f"/tags/{system_id}", json={"name": "X"}).status_code == 403
        assert client.delete(f"/tags/{system_id}").status_code == 403


def test_deleting_a_tag_removes_its_assignments() -> None:
    with TestClient(create_app()) as client:
        client.post("/tags", json={"name": "Doomed"})
        with SessionLocal() as session:
            track = Track(song_id="tags_doomed_1", title="Doomed carrier")
            session.add(track)
            doomed = session.scalar(select(Tag).where(Tag.name == "Doomed"))
            session.flush()
            session.add(TrackTag(track_id=track.id, tag_id=doomed.id, owner_config_id=None))
            session.commit()
            tag_id, track_id = doomed.id, track.id
        assert client.delete(f"/tags/{tag_id}").status_code == 204
        with SessionLocal() as session:
            remaining = session.scalars(
                select(TrackTag).where(TrackTag.track_id == track_id)
            ).all()
        assert remaining == []
