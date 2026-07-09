"""Request-security: CSRF refusal of cross-site browser requests, the exposed-mode authenticated
access model (a spoofed profile id is not honoured; a valid token is), embed-id validation on the
direct write path, secret-file permissions, security headers, and the removed home-path leak."""

from __future__ import annotations

import os
import stat

from fastapi.testclient import TestClient
from sqlalchemy import select

from harmonica.api import create_app
from harmonica.config import Settings, get_settings
from harmonica.db import SessionLocal
from harmonica.models import MediaAsset, Track

YT_ID = "dQw4w9WgXcQ"


def _import_track(client: TestClient, song_id: str) -> int:
    payload = {
        "payload": {
            "rating_factors": [],
            "groups": [],
            "tracks": [{"song_id": song_id, "title": f"Song {song_id}"}],
        }
    }
    assert client.post("/library/import-json", json=payload).status_code == 200
    return next(t for t in client.get("/tracks").json() if t["song_id"] == song_id)["id"]


def test_security_headers_and_no_home_leak() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/settings")
        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        # The absolute home path must no longer be exposed.
        assert "home" not in response.json()


def test_csrf_blocks_cross_site_state_change() -> None:
    with TestClient(create_app()) as client:
        body = {"values": {"beta": 1.3}}
        # A cross-site browser request is refused...
        blocked = client.patch("/settings", json=body, headers={"Sec-Fetch-Site": "cross-site"})
        assert blocked.status_code == 403
        # ...a same-origin one is allowed...
        ok = client.patch("/settings", json=body, headers={"Sec-Fetch-Site": "same-origin"})
        assert ok.status_code == 200
        # ...and a non-browser client (no Sec-Fetch metadata, like curl) is unaffected.
        assert client.patch("/settings", json=body).status_code == 200


def test_csrf_blocks_cross_site_spotify_get() -> None:
    with TestClient(create_app()) as client:
        # The sensitive GET is CSRF-protected too, refused before it does anything.
        blocked = client.get(
            "/spotify/playlist",
            params={"url": "x"},
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert blocked.status_code == 403


def test_exposed_mode_requires_token() -> None:
    app = create_app()
    app.state.auth_required = True  # simulate a NAS bound off loopback
    with TestClient(app) as client:
        # Public bootstrap endpoints stay reachable so the app and claim screen can load.
        assert client.get("/settings").status_code == 200
        assert client.get("/configs").status_code == 200
        # Private reads and any write are refused without a token.
        assert client.get("/tracks").status_code == 401
        assert client.patch("/settings", json={"values": {"beta": 1.3}}).status_code == 401
        # A spoofed profile-id header is NOT honoured in exposed mode.
        assert client.get("/tracks", headers={"X-Harmonica-Config-Id": "1"}).status_code == 401


def test_exposed_mode_valid_token_grants_access() -> None:
    app = create_app()
    app.state.auth_required = True
    with TestClient(app) as client:
        # Creating/claiming a profile is how you obtain a token, so it stays open (with CSRF).
        created = client.post(
            "/configs",
            json={"name": "nas-user", "passphrase": "hunter2", "track_ids": []},
        )
        assert created.status_code == 200
        token = created.json()["token"]
        assert token
        # The token unlocks the private endpoints; the same request without it is refused.
        assert client.get("/tracks").status_code == 401
        auth = {"Authorization": f"Bearer {token}"}
        assert client.get("/tracks", headers=auth).status_code == 200
        # A forged token is rejected.
        forged = {"Authorization": "Bearer 1.deadbeef"}
        assert client.get("/tracks", headers=forged).status_code == 401


def test_embed_direct_id_must_be_well_formed() -> None:
    with TestClient(create_app()) as client:
        track_id = _import_track(client, "sec_embed_1")
        # A bogus directly-supplied external_id is dropped, not stored.
        bad = client.patch(
            f"/tracks/{track_id}",
            json={"embeds": [{"provider": "youtube", "external_id": "not a real id!!"}]},
        )
        assert bad.status_code == 200
        assert bad.json()["embeds"] == []
        # A well-formed one is accepted.
        good = client.patch(
            f"/tracks/{track_id}",
            json={"embeds": [{"provider": "youtube", "external_id": YT_ID}]},
        )
        assert good.status_code == 200
        assert [e["external_id"] for e in good.json()["embeds"]] == [YT_ID]


def test_media_range_request_still_seeks(tmp_path) -> None:
    # The security middleware is pure-ASGI so it must NOT buffer the body: a Range request (how a
    # browser seeks in audio/video) must still return 206 Partial Content with the right bytes.
    media_root = tmp_path / "media"
    media_root.mkdir()
    song = media_root / "song.m4a"
    song.write_bytes(bytes(range(20)))  # 0x00..0x13

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(media_root=media_root)
    with TestClient(app) as client:
        with SessionLocal() as session:
            track = session.scalar(select(Track).where(Track.song_id == "range_test"))
            if track is None:
                track = Track(song_id="range_test", title="Range")
                session.add(track)
                session.flush()
            for stale in list(track.assets):
                session.delete(stale)
            session.flush()
            asset = MediaAsset(track_id=track.id, file_path=str(song), asset_type="audio")
            session.add(asset)
            session.commit()
            asset_id = asset.id

        response = client.get(f"/media/{asset_id}", headers={"Range": "bytes=4-9"})
        assert response.status_code == 206
        assert response.headers.get("content-range") == "bytes 4-9/20"
        assert response.content == bytes(range(4, 10))
        # Security headers ride along on the streamed response too.
        assert "Content-Security-Policy" in response.headers
    app.dependency_overrides.clear()


def test_secret_key_file_is_private() -> None:
    with TestClient(create_app()):
        key_path = get_settings().home / "secret.key"
        assert key_path.exists()
        mode = stat.S_IMODE(os.stat(key_path).st_mode)
        # No group/other bits — owner read/write only (best effort; skip on odd filesystems).
        if hasattr(os, "chmod"):
            assert mode & 0o077 == 0
