"""Optional YouTube embeds: URL parsing, import/export round-trip, and — crucially — the Data API
key is exposed only as a presence boolean, never as a value the browser can read."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from harmonica.api import create_app
from harmonica.config import get_settings
from harmonica.embeds import parse_embed_url


@pytest.mark.parametrize(
    "url,external_id,start",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", None),
        ("https://youtu.be/dQw4w9WgXcQ?t=43", "dQw4w9WgXcQ", 43.0),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m30s", "dQw4w9WgXcQ", 90.0),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", None),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ?start=10", "dQw4w9WgXcQ", 10.0),
    ],
)
def test_parse_youtube_urls(url: str, external_id: str, start: float | None) -> None:
    parsed = parse_embed_url(url)
    assert parsed is not None
    assert parsed.provider == "youtube"
    assert parsed.external_id == external_id
    assert parsed.start_seconds == start


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/watch?v=dQw4w9WgXcQ",  # not a YouTube host
        "https://www.youtube.com/watch?v=tooShort",  # id isn't 11 chars
        "not a url at all",
        "",
    ],
)
def test_parse_rejects_non_embeds(url: str) -> None:
    assert parse_embed_url(url) is None


def _payload_with_embed(song_id: str, url: str) -> dict:
    return {
        "payload": {
            "rating_factors": [],
            "groups": [],
            "tracks": [
                {
                    "song_id": song_id,
                    "title": f"Song {song_id}",
                    "embeds": [{"url": url}],
                }
            ],
        }
    }


def test_embed_round_trips_through_import_and_export() -> None:
    with TestClient(create_app()) as client:
        song_id = "emb_rt_1"
        imported = client.post(
            "/library/import-json",
            json=_payload_with_embed(song_id, "https://youtu.be/dQw4w9WgXcQ?t=30"),
        )
        assert imported.status_code == 200

        track = next(t for t in client.get("/tracks").json() if t["song_id"] == song_id)
        assert len(track["embeds"]) == 1
        embed = track["embeds"][0]
        assert embed["provider"] == "youtube"
        assert embed["external_id"] == "dQw4w9WgXcQ"
        assert embed["start_seconds"] == 30.0

        export = client.get("/library/export-json").json()
        exported = next(t for t in export["tracks"] if t["song_id"] == song_id)
        assert exported["embeds"][0]["external_id"] == "dQw4w9WgXcQ"


def test_youtube_config_reports_state_and_never_leaks_the_key() -> None:
    with TestClient(create_app()) as client:
        cfg = client.get("/youtube/config").json()
        assert cfg["enabled"] is False
        assert cfg["has_api_key"] is False
        assert "youtube" in cfg["providers"]

        secret = "SUPER-SECRET-YT-KEY-abc123"
        key_path = get_settings().home / "youtube_data_api.key"
        key_path.write_text(secret, encoding="utf-8")
        try:
            assert client.get("/youtube/config").json()["has_api_key"] is True
            # The key value itself must never reach the client, anywhere.
            assert secret not in client.get("/youtube/config").text
            assert secret not in client.get("/settings").text
            assert secret not in client.get("/library/export-json").text
        finally:
            key_path.unlink(missing_ok=True)
