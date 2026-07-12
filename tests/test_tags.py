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


def _seed_track(song_id: str, title: str) -> int:
    with SessionLocal() as session:
        track = Track(song_id=song_id, title=title)
        session.add(track)
        session.commit()
        return track.id


def _make_profile(client: TestClient, name: str) -> tuple[int, str]:
    created = client.post(
        "/configs", json={"name": name, "passphrase": "pw-" + name, "track_ids": []}
    )
    if created.status_code == 409:
        created = client.post("/configs/claim", json={"name": name, "passphrase": "pw-" + name})
    body = created.json()
    return body["id"], body["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_track_tags_roundtrip_and_favourite_sync() -> None:
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_rt_1", "Roundtrip")
        saved = client.patch(
            f"/tracks/{track_id}", json={"tags": ["Fun", "Brand New", FAVOURITE_TAG_NAME]}
        )
        assert saved.status_code == 200
        body = saved.json()
        assert set(body["tags"]) == {"Fun", "Brand New", FAVOURITE_TAG_NAME}
        assert body["favourite"] is True  # tag write synced the boolean
        with SessionLocal() as session:
            assert session.get(Track, track_id).favourite is True
            created = session.scalar(select(Tag).where(Tag.name == "Brand New"))
            assert created is not None and created.kind == "custom"

        # Removing Favourite from the list clears the boolean too.
        cleared = client.patch(f"/tracks/{track_id}", json={"tags": ["Fun"]}).json()
        assert cleared["favourite"] is False and cleared["tags"] == ["Fun"]

        # The reverse direction: the plain favourite boolean writes the tag row.
        starred = client.patch(f"/tracks/{track_id}", json={"favourite": True}).json()
        assert FAVOURITE_TAG_NAME in starred["tags"]


def test_per_profile_tags_are_private_and_shared_tags_are_household() -> None:
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_scope_1", "Scoped")
        id_a, token_a = _make_profile(client, "tags-alice")
        _, token_b = _make_profile(client, "tags-bob")
        # Both profiles need the track in their library to see it at all.
        for token in (token_a, token_b):
            client.post(
                "/library/import-json",
                json={"payload": {"tracks": [{"song_id": "tags_scope_1", "title": "Scoped"}]}},
                headers=_auth(token),
            )
        client.post("/tags", json={"name": "No Lyrics", "shared": True})

        client.patch(
            f"/tracks/{track_id}",
            json={"tags": ["Fun", "No Lyrics"]},
            headers=_auth(token_a),
        )
        seen_by_a = client.get(f"/tracks/{track_id}", headers=_auth(token_a)).json()["tags"]
        seen_by_b = client.get(f"/tracks/{track_id}", headers=_auth(token_b)).json()["tags"]
        assert set(seen_by_a) == {"Fun", "No Lyrics"}
        assert seen_by_b == ["No Lyrics"]  # A's per-profile Fun is private; shared is not

        # B removes the shared assignment for the whole household, never A's private one.
        client.patch(f"/tracks/{track_id}", json={"tags": []}, headers=_auth(token_b))
        assert client.get(f"/tracks/{track_id}", headers=_auth(token_a)).json()["tags"] == [
            "Fun"
        ]
