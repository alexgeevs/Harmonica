"""Unified tags: system tags (Favourite, Ignored), starter custom tags, per-profile and shared
assignments, tag-restricted queues, and the light zero-mean pacing layer."""

from __future__ import annotations

import math

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from harmonica.algorithm import (
    AlgorithmTrack,
    apply_tag_pacing,
    generate_playlist,
    tag_pacing_factor,
)
from harmonica.api import create_app
from harmonica.config import Settings
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
        tag = session.scalar(select(Tag).where(Tag.name == "Focused"))
        assert tag is not None  # a real default, so the reseed check below means something
        session.delete(tag)
        session.commit()
    seed_and_backfill_tags(engine)
    with SessionLocal() as session:
        assert session.scalar(select(Tag).where(Tag.name == "Focused")) is None


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


def _run_track_ids(client: TestClient, seed: str, tags: list[str] | None = None) -> list[int]:
    body: dict = {"length": 12, "seed": seed, "explain": False, "ui_active": False}
    if tags is not None:
        body["tags"] = tags
    run = client.post("/queue/generate", json=body)
    assert run.status_code == 200
    return [item["track"]["id"] for item in run.json()["items"]]


def test_ignored_tracks_never_enter_generated_queues() -> None:
    # Deterministic pool: restrict generation to one unique tag carried by kept + dropped,
    # so the assertion cannot flake against tracks other test files seeded into the shared DB.
    # This also proves ignored wins over an explicit tag restriction.
    with TestClient(create_app()) as client:
        kept = [_seed_track(f"tags_ign_keep_{i}", f"Keep {i}") for i in range(3)]
        dropped = _seed_track("tags_ign_drop", "Dropped")
        for track_id in kept:
            client.patch(f"/tracks/{track_id}", json={"tags": ["Ignore Pool"]})
        client.patch(f"/tracks/{dropped}", json={"tags": ["Ignore Pool", IGNORED_TAG_NAME]})
        played = set(_run_track_ids(client, seed="ignored-seed", tags=["Ignore Pool"]))
        assert dropped not in played
        assert played and played <= set(kept)


def test_ignored_is_profile_scoped_and_excluded_for_that_profile() -> None:
    # Bob ignores a shared song: it vanishes from HIS generated queues only. Alice's view and
    # queues are untouched, because Ignored assignments are per-profile like favourites.
    with TestClient(create_app()) as client:
        _, token_a = _make_profile(client, "tags-ign-alice")
        _, token_b = _make_profile(client, "tags-ign-bob")
        payload = {
            "tracks": [
                {"song_id": f"tags_pign_{i}", "title": f"Shared {i}"} for i in range(3)
            ]
        }
        for token in (token_a, token_b):
            client.post("/library/import-json", json={"payload": payload}, headers=_auth(token))
        with SessionLocal() as session:
            target = session.scalar(
                select(Track.id).where(Track.song_id == "tags_pign_0")
            )
        client.patch(
            f"/tracks/{target}", json={"tags": [IGNORED_TAG_NAME]}, headers=_auth(token_b)
        )

        def owned_run(token: str) -> set[int]:
            run = client.post(
                "/queue/generate",
                json={"length": 30, "seed": "pign", "explain": False, "ui_active": False},
                headers=_auth(token),
            )
            assert run.status_code == 200
            return {item["track"]["id"] for item in run.json()["items"]}

        assert target not in owned_run(token_b)
        assert target in owned_run(token_a)
        assert IGNORED_TAG_NAME not in client.get(
            f"/tracks/{target}", headers=_auth(token_a)
        ).json()["tags"]


def test_queue_restricted_to_tag_union() -> None:
    with TestClient(create_app()) as client:
        fun = [_seed_track(f"tags_union_fun_{i}", f"Fun {i}") for i in range(2)]
        calm = _seed_track("tags_union_calm", "Calm one")
        other = _seed_track("tags_union_other", "Untagged")
        # Unique tag names: the suite shares one DB, so reusing seeded names like "Fun" would
        # legitimately pull in other tests' tracks.
        for track_id in fun:
            client.patch(f"/tracks/{track_id}", json={"tags": ["Union Fun"]})
        client.patch(f"/tracks/{calm}", json={"tags": ["Union Calm"]})
        played = set(_run_track_ids(client, seed="union-seed", tags=["Union Fun", "Union Calm"]))
        assert played <= set(fun) | {calm}
        assert other not in played
        only_fun = set(_run_track_ids(client, seed="union-seed", tags=["Union Fun"]))
        assert only_fun <= set(fun)


def test_unknown_tag_restriction_yields_empty_run() -> None:
    with TestClient(create_app()) as client:
        _seed_track("tags_unknown_1", "Present")
        assert _run_track_ids(client, seed="s", tags=["No Such Tag"]) == []


def _algo_track(track_id: int, tags: frozenset[str] = frozenset()) -> AlgorithmTrack:
    return AlgorithmTrack(
        id=track_id,
        song_id=f"algo_{track_id}",
        title=f"Algo {track_id}",
        artist=None,
        album=None,
        media_asset_id=None,
        file_path=None,
        tags=tags,
    )


def test_tag_pacing_factor_is_zero_mean_and_directional() -> None:
    horizon = 12
    for bias in (-1.0, -0.4, 0.6, 1.0):
        total = sum(
            tag_pacing_factor(d, horizon, bias) - 1.0 for d in range(1, horizon)
        )
        assert math.isclose(total, 0.0, abs_tol=1e-9)
    # Negative bias: suppressed just after a play, compensated later in the horizon.
    assert tag_pacing_factor(1, horizon, -1.0) < 1.0
    assert tag_pacing_factor(horizon - 1, horizon, -1.0) > 1.0
    # Positive bias mirrors it; inert cases are exactly 1.0.
    assert tag_pacing_factor(1, horizon, 1.0) > 1.0
    assert tag_pacing_factor(None, horizon, 1.0) == 1.0
    assert tag_pacing_factor(horizon, horizon, 1.0) == 1.0
    assert tag_pacing_factor(3, horizon, 0.0) == 1.0


def test_apply_tag_pacing_moves_only_tagged_tracks() -> None:
    tracks = [
        _algo_track(1, frozenset({"Fun"})),
        _algo_track(2, frozenset({"Fun"})),
        _algo_track(3),
    ]
    scores = [1.0, 1.0, 1.0]
    settings = Settings(tag_clustering_bias=-1.0)
    adjusted = apply_tag_pacing(tracks, scores, 1, {"Fun": 0}, settings)
    assert adjusted[0] < 1.0 and adjusted[1] < 1.0  # same-tag, just played: suppressed
    assert adjusted[2] == 1.0  # untagged: untouched
    # Bias 0 short-circuits to the same list object (byte parity).
    neutral = Settings(tag_clustering_bias=0.0)
    assert apply_tag_pacing(tracks, scores, 1, {"Fun": 0}, neutral) is scores


def test_bias_zero_is_byte_identical_with_tags_present() -> None:
    tagged = [_algo_track(i, frozenset({"Fun"}) if i % 2 else frozenset()) for i in range(8)]
    bare = [_algo_track(i) for i in range(8)]
    settings = Settings(tag_clustering_bias=0.0)
    run_tagged = generate_playlist(tagged, {}, 30, settings, seed="parity")
    run_bare = generate_playlist(bare, {}, 30, settings, seed="parity")
    assert [item.track.id for item in run_tagged] == [item.track.id for item in run_bare]


def test_negative_bias_spaces_same_tag_songs_apart() -> None:
    # Half the pool shares one algorithm-active tag; count adjacent same-tag pairs, summed over
    # a few fixed seeds so the deterministic comparison is not hostage to one lucky draw.
    def adjacency(bias: float) -> int:
        total = 0
        for seed in ("spacing-a", "spacing-b", "spacing-c"):
            tracks = [
                _algo_track(i, frozenset({"Fun"}) if i < 10 else frozenset())
                for i in range(20)
            ]
            settings = Settings(tag_clustering_bias=bias)
            items = generate_playlist(tracks, {}, 120, settings, seed=seed)
            flags = [item.track.id < 10 for item in items]
            total += sum(1 for a, b in zip(flags, flags[1:], strict=False) if a and b)
        return total

    assert adjacency(-1.0) < adjacency(0.0) < adjacency(1.0)


def test_profile_delete_keeps_other_profiles_tag() -> None:
    # Deleting a tag as a profile removes it for that profile only. The definition survives
    # while anyone else still uses it, and finally goes once nobody does.
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_del_scope_1", "Delete scoped")
        _, token_a = _make_profile(client, "tags-del-alice")
        _, token_b = _make_profile(client, "tags-del-bob")
        payload = {"tracks": [{"song_id": "tags_del_scope_1", "title": "Delete scoped"}]}
        for token in (token_a, token_b):
            client.post("/library/import-json", json={"payload": payload}, headers=_auth(token))
            client.patch(
                f"/tracks/{track_id}", json={"tags": ["Household Fav"]}, headers=_auth(token)
            )
        tag_id = next(
            t["id"] for t in client.get("/tags").json() if t["name"] == "Household Fav"
        )
        assert client.delete(f"/tags/{tag_id}", headers=_auth(token_a)).status_code == 204
        seen_by_a = client.get(f"/tracks/{track_id}", headers=_auth(token_a)).json()["tags"]
        seen_by_b = client.get(f"/tracks/{track_id}", headers=_auth(token_b)).json()["tags"]
        assert "Household Fav" not in seen_by_a
        assert "Household Fav" in seen_by_b
        assert any(t["name"] == "Household Fav" for t in client.get("/tags").json())
        assert client.delete(f"/tags/{tag_id}", headers=_auth(token_b)).status_code == 204
        assert not any(t["name"] == "Household Fav" for t in client.get("/tags").json())


def test_unsharing_keeps_the_tag_in_every_account() -> None:
    # Alice tags a song under a shared tag, then unshares it. Bob, Alice and local mode all
    # keep their own copy, and Alice deleting hers afterwards leaves Bob's alone.
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_unshare_1", "Unshared")
        _, token_a = _make_profile(client, "tags-unshare-alice")
        _, token_b = _make_profile(client, "tags-unshare-bob")
        payload = {"tracks": [{"song_id": "tags_unshare_1", "title": "Unshared"}]}
        for token in (token_a, token_b):
            client.post("/library/import-json", json={"payload": payload}, headers=_auth(token))
        shared = client.post("/tags", json={"name": "Karaoke", "shared": True}).json()
        client.patch(f"/tracks/{track_id}", json={"tags": ["Karaoke"]}, headers=_auth(token_a))

        client.patch(f"/tags/{shared['id']}", json={"shared": False})
        for token in (token_a, token_b):
            assert "Karaoke" in client.get(
                f"/tracks/{track_id}", headers=_auth(token)
            ).json()["tags"]
        assert "Karaoke" in client.get(f"/tracks/{track_id}").json()["tags"]  # local mode

        assert client.delete(f"/tags/{shared['id']}", headers=_auth(token_a)).status_code == 204
        assert "Karaoke" not in client.get(
            f"/tracks/{track_id}", headers=_auth(token_a)
        ).json()["tags"]
        assert "Karaoke" in client.get(f"/tracks/{track_id}", headers=_auth(token_b)).json()[
            "tags"
        ]


def test_profile_cannot_delete_shared_tag() -> None:
    with TestClient(create_app()) as client:
        _, token_a = _make_profile(client, "tags-shared-del")
        created = client.post("/tags", json={"name": "House Rules", "shared": True}).json()
        assert client.delete(f"/tags/{created['id']}", headers=_auth(token_a)).status_code == 403
        assert any(t["name"] == "House Rules" for t in client.get("/tags").json())


def test_export_import_roundtrip_carries_tags() -> None:
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_exp_1", "Exported")
        client.post("/tags", json={"name": "Sing Along", "affects_algorithm": True})
        client.patch(f"/tracks/{track_id}", json={"tags": ["Sing Along", IGNORED_TAG_NAME]})
        payload = client.get("/library/export-json?scope=metadata").json()
        tag_block = payload["tags"]
        assert {"song_id": "tags_exp_1", "tag": "Sing Along"} in tag_block["assignments"]
        sing = next(d for d in tag_block["definitions"] if d["name"] == "Sing Along")
        assert sing["affects_algorithm"] is True

        # Re-importing the same payload is idempotent.
        first = client.post("/library/import-json", json={"payload": payload}).json()
        assert first["tags_applied"] == 0
        with SessionLocal() as session:
            rows = session.scalars(
                select(TrackTag).where(TrackTag.track_id == track_id)
            ).all()
        assert len(rows) == 2


def test_legacy_favourite_import_syncs_the_tag() -> None:
    with TestClient(create_app()) as client:
        payload = {
            "tracks": [{"song_id": "tags_legacy_1", "title": "Legacy", "favourite": True}]
        }
        client.post("/library/import-json", json={"payload": payload})
        with SessionLocal() as session:
            track = session.scalar(select(Track).where(Track.song_id == "tags_legacy_1"))
            tags = visible_tags_by_track(session, None).get(track.id, [])
        assert FAVOURITE_TAG_NAME in tags
