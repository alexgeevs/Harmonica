"""Per-user multi-tenancy: private libraries + listening data, shared deduplicated media.

A profile (DeviceConfig) is a user. With its bearer token, a request sees only that profile's
library, playback history, ratings, queues and cover verdicts; with no header the daemon stays in
legacy/local whole-library mode (byte-identical to before — covered by the rest of the suite)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from harmonica.api import create_app
from harmonica.db import SessionLocal
from harmonica.models import DeviceConfigTrack, RatingSample, Track


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_profile(client: TestClient, name: str) -> tuple[int, str]:
    """Create a fresh empty profile, returning (id, token). Idempotent across re-runs."""
    created = client.post(
        "/configs", json={"name": name, "passphrase": "pw-" + name, "track_ids": []}
    )
    if created.status_code == 409:
        created = client.post("/configs/claim", json={"name": name, "passphrase": "pw-" + name})
    body = created.json()
    return body["id"], body["token"]


def _library_payload(song_ids: list[str]) -> dict:
    return {
        "rating_factors": [],
        "groups": [],
        "tracks": [
            {
                "song_id": song_id,
                "title": f"Song {song_id}",
                "assets": [
                    {
                        "file_path": f"/srv/media/{song_id}.m4a",
                        "asset_type": "audio",
                        "checksum": f"sum-{song_id}",
                        "browser_supported": True,
                    }
                ],
            }
            for song_id in song_ids
        ],
    }


def _track_id(song_id: str) -> int:
    with SessionLocal() as session:
        return session.scalar(select(Track.id).where(Track.song_id == song_id))


def test_libraries_and_listening_data_are_private_per_profile() -> None:
    songs = ["mt_iso_1", "mt_iso_2"]
    with TestClient(create_app()) as client:
        _, token_a = _make_profile(client, "mt-alice")
        _, token_b = _make_profile(client, "mt-bob")

        # Alice imports a two-song library; Bob imports nothing.
        imported = client.post(
            "/library/import-json",
            json={"payload": _library_payload(songs)},
            headers=_auth(token_a),
        )
        assert imported.status_code == 200

        alice_titles = {t["song_id"] for t in client.get("/tracks", headers=_auth(token_a)).json()}
        assert set(songs) <= alice_titles
        # Bob's library is empty — he can't see Alice's songs.
        assert client.get("/tracks", headers=_auth(token_b)).json() == []

        track_id = _track_id(songs[0])
        # Bob can't even read one of Alice's tracks by id.
        assert client.get(f"/tracks/{track_id}", headers=_auth(token_b)).status_code == 404
        assert client.get(f"/tracks/{track_id}", headers=_auth(token_a)).status_code == 200

        # Playback history is private.
        client.post(
            "/playback-events",
            json={"event_type": "completed", "track_id": track_id, "duration_seconds": 100},
            headers=_auth(token_a),
        )
        assert len(client.get("/playback-events", headers=_auth(token_a)).json()) == 1
        assert client.get("/playback-events", headers=_auth(token_b)).json() == []

        # Stats are scoped to each profile's own library.
        assert client.get("/stats/summary", headers=_auth(token_a)).json()["track_count"] >= 2
        assert client.get("/stats/summary", headers=_auth(token_b)).json()["track_count"] == 0


def test_import_dedupes_and_redirects_to_shared_track() -> None:
    songs = ["mt_dedupe_1", "mt_dedupe_2"]
    with TestClient(create_app()) as client:
        _, token_a = _make_profile(client, "mt-dd-a")
        _, token_b = _make_profile(client, "mt-dd-b")
        payload = {"payload": _library_payload(songs)}

        client.post("/library/import-json", json=payload, headers=_auth(token_a))
        client.post("/library/import-json", json=payload, headers=_auth(token_b))

        with SessionLocal() as session:
            # One shared Track per song (not one per importer)...
            for song_id in songs:
                count = session.scalar(
                    select(func.count()).select_from(Track).where(Track.song_id == song_id)
                )
                assert count == 1
            # ...but a private library link for each of the two profiles.
            track_id = session.scalar(select(Track.id).where(Track.song_id == songs[0]))
            links = session.scalar(
                select(func.count())
                .select_from(DeviceConfigTrack)
                .where(DeviceConfigTrack.track_id == track_id)
            )
            assert links == 2

        # Both profiles see the songs in their own library.
        assert len(client.get("/tracks", headers=_auth(token_a)).json()) >= 2
        assert len(client.get("/tracks", headers=_auth(token_b)).json()) >= 2


def test_ratings_are_private_per_profile() -> None:
    songs = ["mt_rate_1"]
    with TestClient(create_app()) as client:
        _, token_a = _make_profile(client, "mt-rate-a")
        _, token_b = _make_profile(client, "mt-rate-b")
        payload = {"payload": _library_payload(songs)}
        client.post("/library/import-json", json=payload, headers=_auth(token_a))
        client.post("/library/import-json", json=payload, headers=_auth(token_b))
        track_id = _track_id(songs[0])

        client.patch(
            f"/tracks/{track_id}", json={"ratings": {"overall": 5}}, headers=_auth(token_a)
        )
        client.patch(
            f"/tracks/{track_id}", json={"ratings": {"overall": 1}}, headers=_auth(token_b)
        )

        a_view = client.get(f"/tracks/{track_id}", headers=_auth(token_a)).json()
        b_view = client.get(f"/tracks/{track_id}", headers=_auth(token_b)).json()
        assert a_view["ratings"].get("overall") == 5.0
        assert b_view["ratings"].get("overall") == 1.0


def test_idempotent_import_does_not_duplicate_history() -> None:
    songs = ["mt_idem_1"]
    with TestClient(create_app()) as client:
        config_id, token_a = _make_profile(client, "mt-idem-a")
        payload = {"payload": _library_payload(songs)}
        client.post("/library/import-json", json=payload, headers=_auth(token_a))
        track_id = _track_id(songs[0])
        client.patch(
            f"/tracks/{track_id}", json={"ratings": {"overall": 4}}, headers=_auth(token_a)
        )

        # Export Alice's library (with her rating history) and re-import it twice.
        export = client.get("/library/export-json", headers=_auth(token_a)).json()
        for _ in range(2):
            client.post("/library/import-json", json={"payload": export}, headers=_auth(token_a))

        with SessionLocal() as session:
            samples = session.scalar(
                select(func.count())
                .select_from(RatingSample)
                .where(
                    RatingSample.track_id == track_id,
                    RatingSample.owner_config_id == config_id,
                )
            )
        assert samples == 1  # one rating action, no duplicates from re-import


def test_new_profile_generates_empty_queue_without_crashing() -> None:
    with TestClient(create_app()) as client:
        _, token = _make_profile(client, "mt-empty")
        run = client.post("/queue/generate", json={"length": 10}, headers=_auth(token))
        assert run.status_code == 200
        assert run.json()["items"] == []


def test_saved_queues_are_private_per_profile() -> None:
    songs = ["mt_queue_1", "mt_queue_2"]
    with TestClient(create_app()) as client:
        _, token_a = _make_profile(client, "mt-q-a")
        _, token_b = _make_profile(client, "mt-q-b")
        client.post(
            "/library/import-json",
            json={"payload": _library_payload(songs)},
            headers=_auth(token_a),
        )
        client.post("/queue/generate", json={"length": 5}, headers=_auth(token_a))
        # Alice has a run; Bob sees none of it.
        assert len(client.get("/playlist-runs", headers=_auth(token_a)).json()) >= 1
        assert client.get("/playlist-runs", headers=_auth(token_b)).json() == []


def test_forged_or_missing_token_is_handled() -> None:
    with TestClient(create_app()) as client:
        _, token = _make_profile(client, "mt-auth")
        # A token with a tampered signature is rejected.
        forged = token.split(".", 1)[0] + ".deadbeef"
        assert client.get("/tracks", headers=_auth(forged)).status_code == 401
        # No header at all is legacy/local mode (whole library), not an error.
        assert client.get("/tracks").status_code == 200
