"""The YouTube video-list importer: link extraction, keyless (oEmbed) and keyed (Data API) metadata
reads through an injected fake transport (never the network), the organising into proposed tracks
and confirm-first clusters, and the endpoint's gating (feature off, and key-required factors without
a key)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from harmonica import api as api_module
from harmonica.api import create_app
from harmonica.youtube_import import (
    VideoMeta,
    extract_video_ids,
    fetch_via_data_api,
    fetch_via_oembed,
    normalise_factors,
    requires_api_key,
)
from harmonica.youtube_organize import organize


class FakeTransport:
    """Serves canned JSON keyed by a substring of the requested URL, and records the calls."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        self.calls.append((url, headers))
        for needle, payload in self._responses.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected url {url}")


def test_extract_video_ids_dedups_and_ignores_junk() -> None:
    text = """
    https://www.youtube.com/watch?v=dQw4w9WgXcQ
    https://youtu.be/9bZkp7q19f0?t=42
    plainly not a link
    kJQP7kiw5Fk
    https://www.youtube.com/watch?v=dQw4w9WgXcQ
    """
    assert extract_video_ids(text) == ["dQw4w9WgXcQ", "9bZkp7q19f0", "kJQP7kiw5Fk"]


def test_factor_gating() -> None:
    assert requires_api_key(normalise_factors(["channel", "title"])) is False
    assert requires_api_key(normalise_factors(["duration"])) is True
    # Unknown factors are dropped; the keyless basics are always present.
    assert normalise_factors(["bogus"]) == {"channel", "title"}


class _OembedTransport:
    """A video id containing 'bad' is treated as unreadable (private/deleted); others resolve."""

    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        if "bad" in url:
            from harmonica.youtube_import import YouTubeImportError

            raise YouTubeImportError("A video was not found")
        return {"title": "Song - Artist", "author_name": "Chan"}


def test_oembed_skips_unreadable_but_keeps_the_rest() -> None:
    # oEmbed builds the request url from the watch url, which contains the video id.
    metas = fetch_via_oembed(["goodgoodgoo", "badbadbadba"], transport=_OembedTransport())
    assert [m.available for m in metas] == [True, False]
    assert metas[0].title == "Song - Artist"


def test_data_api_batches_and_parses_duration() -> None:
    payload = {
        "items": [
            {
                "id": "aaaaaaaaaaa",
                "snippet": {"title": "Hello", "channelTitle": "Adele"},
                "contentDetails": {"duration": "PT4M13S"},
            }
        ]
    }
    transport = FakeTransport({"videos": payload})
    metas = fetch_via_data_api(["aaaaaaaaaaa", "zzzzzzzzzzz"], "secret-key", transport=transport)
    assert metas[0].duration_seconds == 4 * 60 + 13
    assert metas[1].available is False  # absent from the response => unavailable
    # The key travels as a header, never in the URL.
    url, headers = transport.calls[0]
    assert "secret-key" not in url
    assert headers.get("X-goog-api-key") == "secret-key"


def test_organize_stage_one_and_clusters() -> None:
    metas = [
        VideoMeta("aaaaaaaaaaa", title="Adele - Hello (Official Video)", channel="Adele"),
        VideoMeta("bbbbbbbbbbb", title="Hello - Adele [Live]", channel="Fan"),
        VideoMeta("ccccccccccc", title="Solo Song", channel="Artist - Topic"),
    ]
    result = organize(metas, normalise_factors(["channel", "title"]))
    assert len(result.tracks) == 3
    # Artist/title parsed and the auto-generated " - Topic" channel suffix stripped.
    solo = next(t for t in result.tracks if t["song_id"] == "yt:ccccccccccc")
    assert solo["groups"][0]["name"] == "Artist"
    # The order-swapped duplicate clusters, and it is only a suggestion (kept separate).
    assert any(
        set(c.song_ids) == {"yt:aaaaaaaaaaa", "yt:bbbbbbbbbbb"} for c in result.clusters
    )


def _enable_youtube(client: TestClient) -> None:
    assert client.patch(
        "/settings", json={"values": {"youtube_embed_enabled": True}}
    ).status_code == 200


def test_endpoint_refused_when_feature_off() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/youtube/import-preview",
            json={"links": "https://youtu.be/dQw4w9WgXcQ", "factors": ["title"]},
        )
        assert response.status_code == 403


def test_endpoint_requires_key_for_key_factors() -> None:
    with TestClient(create_app()) as client:
        _enable_youtube(client)
        response = client.post(
            "/youtube/import-preview",
            json={"links": "https://youtu.be/dQw4w9WgXcQ", "factors": ["duration"]},
        )
        assert response.status_code == 400
        assert "Data API key" in response.json()["detail"]


def test_endpoint_is_csrf_protected() -> None:
    # A POST is state-changing/outbound, so a cross-site browser request is refused before the
    # route runs (the importer must not be drivable from another website on a NAS).
    with TestClient(create_app()) as client:
        blocked = client.post(
            "/youtube/import-preview",
            json={"links": "x", "factors": ["title"]},
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert blocked.status_code == 403


def test_endpoint_needs_token_when_exposed() -> None:
    app = create_app()
    app.state.auth_required = True  # simulate a NAS bound off loopback
    with TestClient(app) as client:
        response = client.post(
            "/youtube/import-preview",
            json={"links": "https://youtu.be/dQw4w9WgXcQ", "factors": ["title"]},
        )
        assert response.status_code == 401


def test_endpoint_keyless_preview(monkeypatch) -> None:
    def fake_oembed(video_ids, *, transport=None):
        return [
            VideoMeta(vid, title=f"Artist - Track {i}", channel="A Channel")
            for i, vid in enumerate(video_ids)
        ]

    monkeypatch.setattr(api_module, "fetch_via_oembed", fake_oembed)
    with TestClient(create_app()) as client:
        _enable_youtube(client)
        response = client.post(
            "/youtube/import-preview",
            json={
                "links": "https://youtu.be/dQw4w9WgXcQ\nhttps://youtu.be/9bZkp7q19f0",
                "factors": ["channel", "title"],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["used_api"] is False
        assert body["requested"] == 2
        assert len(body["tracks"]) == 2
        assert body["tracks"][0]["embeds"][0]["provider"] == "youtube"
