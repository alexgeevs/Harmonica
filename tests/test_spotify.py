"""Read-only Spotify integration: playlist-link parsing, metadata normalisation, token caching,
SSRF guards, and — crucially — the app credentials are only ever exposed as a presence boolean."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from harmonica.api import create_app
from harmonica.config import get_settings
from harmonica.spotify import (
    API_BASE,
    SpotifyError,
    _assert_allowed,
    clear_token_cache,
    fetch_playlist,
    parse_playlist_id,
)

PLAYLIST_ID = "37i9dQZF1DXcBWIGoYBM5M"


@pytest.mark.parametrize(
    "value,expected",
    [
        (f"https://open.spotify.com/playlist/{PLAYLIST_ID}?si=abc123", PLAYLIST_ID),
        (f"spotify:playlist:{PLAYLIST_ID}", PLAYLIST_ID),
        (PLAYLIST_ID, PLAYLIST_ID),
        (f"open.spotify.com/playlist/{PLAYLIST_ID}", PLAYLIST_ID),
        ("https://open.spotify.com/track/abc", None),  # not a playlist
        ("https://evil.example.com/playlist/../secrets", None),  # path junk, wrong host
        ("not a link", None),
        ("", None),
    ],
)
def test_parse_playlist_id(value: str, expected: str | None) -> None:
    assert parse_playlist_id(value) == expected


def _raw_track(index: int) -> dict:
    return {
        "name": f"Song {index}",
        "artists": [{"name": f"Artist {index}"}],
        "album": {"name": f"Album {index}"},
        "duration_ms": 1000 + index,
        "id": f"id{index}",
        "external_urls": {"spotify": f"https://open.spotify.com/track/id{index}"},
    }


class FakeTransport:
    """Stands in for real network I/O so tests never touch Spotify."""

    def __init__(self, raw_tracks: list[dict | None], name: str = "Mix") -> None:
        self.raw_tracks = raw_tracks
        self.name = name
        self.token_calls = 0
        self.track_requests = 0

    def post_form(self, url: str, data: dict, headers: dict) -> dict:
        self.token_calls += 1
        assert data["grant_type"] == "client_credentials"
        assert headers["Authorization"].startswith("Basic ")
        return {"access_token": "tok", "expires_in": 3600}

    def get_json(self, url: str, headers: dict) -> dict:
        assert headers["Authorization"] == "Bearer tok"
        parsed = urlparse(url)
        if parsed.path.endswith("/tracks"):
            self.track_requests += 1
            query = parse_qs(parsed.query)
            offset = int(query["offset"][0])
            limit = int(query["limit"][0])
            chunk = self.raw_tracks[offset : offset + limit]
            return {"items": [{"track": raw} for raw in chunk], "total": len(self.raw_tracks)}
        return {"name": self.name}


def test_fetch_playlist_normalises_and_paginates() -> None:
    clear_token_cache()
    transport = FakeTransport([_raw_track(i) for i in range(150)])
    playlist = fetch_playlist(
        "cid", "secret", f"spotify:playlist:{PLAYLIST_ID}", transport=transport
    )
    assert playlist.id == PLAYLIST_ID
    assert playlist.name == "Mix"
    assert len(playlist.tracks) == 150
    assert playlist.tracks[0].artists == ["Artist 0"]
    assert playlist.tracks[0].album == "Album 0"
    assert playlist.truncated is False
    assert transport.token_calls == 1  # one auth for the whole fetch
    assert transport.track_requests == 2  # 100 + 50 across two pages


def test_fetch_playlist_skips_null_and_nameless_items() -> None:
    clear_token_cache()
    # A removed/local track (None) and a podcast episode (no name) are both dropped.
    transport = FakeTransport([_raw_track(0), None, {"id": "ep", "artists": []}, _raw_track(1)])
    playlist = fetch_playlist("cid", "secret", PLAYLIST_ID, transport=transport)
    assert [track.name for track in playlist.tracks] == ["Song 0", "Song 1"]


def test_fetch_playlist_caps_and_marks_truncated() -> None:
    clear_token_cache()
    transport = FakeTransport([_raw_track(i) for i in range(600)])
    playlist = fetch_playlist("cid", "secret", PLAYLIST_ID, transport=transport)
    assert len(playlist.tracks) == 500
    assert playlist.truncated is True


def test_token_is_reused_across_fetches() -> None:
    clear_token_cache()
    transport = FakeTransport([_raw_track(0)])
    fetch_playlist("cid", "secret", PLAYLIST_ID, transport=transport)
    fetch_playlist("cid", "secret", PLAYLIST_ID, transport=transport)
    assert transport.token_calls == 1  # cached, not re-authenticated


def test_fetch_rejects_bad_link() -> None:
    clear_token_cache()
    transport = FakeTransport([_raw_track(0)])
    with pytest.raises(SpotifyError):
        fetch_playlist("cid", "secret", "https://evil.example.com/x", transport=transport)
    assert transport.token_calls == 0  # rejected before any network


def test_assert_allowed_blocks_non_spotify_hosts() -> None:
    _assert_allowed(f"{API_BASE}/playlists/x")  # ok
    for bad in ("http://169.254.169.254/latest/meta-data", "http://localhost:8765/settings"):
        with pytest.raises(SpotifyError):
            _assert_allowed(bad)


def test_spotify_config_default_is_off_and_credential_free() -> None:
    with TestClient(create_app()) as client:
        config = client.get("/spotify/config").json()
        assert config["enabled"] is False
        assert config["has_credentials"] is False
        # Disabled → the playlist endpoint refuses before doing anything.
        assert client.get("/spotify/playlist", params={"url": PLAYLIST_ID}).status_code == 403


def test_spotify_credentials_never_leak() -> None:
    with TestClient(create_app()) as client:
        home = get_settings().home
        (home / "spotify_client_id.key").write_text("SECRET-CLIENT-ID-xyz", encoding="utf-8")
        (home / "spotify_client_secret.key").write_text(
            "SECRET-CLIENT-SECRET-abc", encoding="utf-8"
        )
        try:
            config = client.get("/spotify/config").json()
            assert config["has_credentials"] is True
            for text in (
                client.get("/spotify/config").text,
                client.get("/settings").text,
                client.get("/library/export-json").text,
            ):
                assert "SECRET-CLIENT-ID-xyz" not in text
                assert "SECRET-CLIENT-SECRET-abc" not in text
        finally:
            (home / "spotify_client_id.key").unlink(missing_ok=True)
            (home / "spotify_client_secret.key").unlink(missing_ok=True)
