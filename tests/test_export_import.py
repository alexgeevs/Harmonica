"""Scoped export and hardened import.

The export can carry just the metadata (songs and groups), just the ratings (stars and
their raw history), just the settings, or everything. The import takes any of those files
back and must stay safe against a hostile file: wrong-typed sections, oversized bodies,
out-of-range values and unknown settings keys are all neutralised, and a crafted
``file_path`` is stored as inert data that /media refuses to serve (covered in
test_security.py)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from harmonica.api import create_app
from harmonica.db import SessionLocal
from harmonica.models import Track, TrackRating


def _seed(client: TestClient, prefix: str) -> None:
    payload = {
        "rating_factors": [{"key": "overall", "label": "Overall", "weight": 1.0}],
        "groups": [{"name": prefix + " Group", "group_type": "other"}],
        "tracks": [
            {
                "song_id": f"{prefix}_song_{i}",
                "title": f"{prefix} Song {i}",
                "artist": "Marlowe Vance",
                "groups": [{"name": prefix + " Group", "group_type": "other"}],
                "assets": [
                    {
                        "file_path": f"/srv/media/{prefix}_{i}.m4a",
                        "asset_type": "audio",
                        "checksum": f"sum-{prefix}-{i}",
                    }
                ],
                "ratings": {"overall": 4.0},
            }
            for i in range(2)
        ],
    }
    response = client.post("/library/import-json", json={"payload": payload})
    assert response.status_code == 200


def test_export_scopes_carry_only_their_sections() -> None:
    client = TestClient(create_app())
    _seed(client, "scope")

    metadata = client.get("/library/export-json", params={"scope": "metadata"}).json()
    assert metadata["scope"] == "metadata"
    assert "tracks" in metadata and "groups" in metadata
    assert "rating_samples" not in metadata and "settings" not in metadata
    assert all("ratings" not in track for track in metadata["tracks"])

    ratings = client.get("/library/export-json", params={"scope": "ratings"}).json()
    assert "tracks" not in ratings and "groups" not in ratings
    assert "rating_factors" in ratings and "rating_samples" in ratings
    starred = {
        entry["song_id"]: entry["ratings"] for entry in ratings.get("track_ratings", [])
    }
    assert starred.get("scope_song_0", {}).get("overall") == 4.0

    settings_export = client.get("/library/export-json", params={"scope": "settings"}).json()
    assert "tracks" not in settings_export
    values = settings_export["settings"]
    assert "beta" in values and "satiation_enabled" in values
    # Never the server's identity or anything credential-shaped.
    for forbidden in ("host", "port", "home", "secret", "api_key", "client_secret"):
        assert all(forbidden not in key for key in values)

    everything = client.get("/library/export-json", params={"scope": "all"}).json()
    for section in ("tracks", "groups", "rating_factors", "rating_samples", "settings"):
        assert section in everything

    assert client.get("/library/export-json", params={"scope": "nonsense"}).status_code == 422


def test_ratings_only_roundtrip_applies_stars_to_existing_tracks() -> None:
    client = TestClient(create_app())
    _seed(client, "rtrip")
    ratings_file = client.get("/library/export-json", params={"scope": "ratings"}).json()

    # Wipe the star, then bring it back from the ratings-only file.
    with SessionLocal() as session:
        track = session.scalar(select(Track).where(Track.song_id == "rtrip_song_0"))
        for rating in session.scalars(
            select(TrackRating).where(TrackRating.track_id == track.id)
        ):
            rating.value = None
        session.commit()

    response = client.post("/library/import-json", json={"payload": ratings_file})
    summary = response.json()
    assert summary["ok"] is True
    assert summary["track_ratings_applied"] >= 1
    with SessionLocal() as session:
        track = session.scalar(select(Track).where(Track.song_id == "rtrip_song_0"))
        values = [rating.value for rating in track.ratings if rating.value is not None]
        assert 4.0 in values


def test_settings_import_applies_only_known_keys_within_range() -> None:
    client = TestClient(create_app())
    payload = {
        "settings": {
            "beta": 99.0,  # above the control's maximum: must clamp, not land raw
            "satiation_enabled": False,
            "secret_key": "attacker",  # not a control: must be ignored
            "host": "0.0.0.0",  # not a control: a file must never re-bind the daemon
            "default_playlist_length": "garbage",  # unparseable: skipped
        }
    }
    summary = client.post("/library/import-json", json={"payload": payload}).json()
    assert summary["settings_applied"] == 2
    settings_now = client.get("/settings").json()
    assert settings_now["beta"] == 3.0
    assert settings_now["satiation_enabled"] is False
    assert settings_now["host"] != "0.0.0.0"


def test_hostile_import_shapes_do_not_crash_or_land() -> None:
    client = TestClient(create_app())
    payload = {
        "tracks": [
            "not-a-dict",
            {"title": "No song id"},
            {"song_id": {"nested": "dict"}},
            {
                "song_id": "hostile_ok",
                "title": {"xss": "<script>alert(1)</script>"},  # wrong type: default used
                "artist": 12345,
                "manual_multiplier": "NaN",
                "clip_start_seconds": "abc",
                "assets": [{"asset_type": "audio"}, "junk"],  # no file_path: dropped
                "cooldown_tags": [{"a": 1}, "", "ok-tag"],
                "ratings": {"overall": 999},
                "groups": "not-a-list",
                "embeds": [{"provider": "youtube", "external_id": "x" * 500}],
            },
        ],
        "rating_factors": {"not": "a list"},
        "groups": [{"group_type": "other"}],
        "rating_samples": [{"song_id": "hostile_ok", "value": {"weird": True}}],
        "settings": "not-a-dict",
        "__proto__": {"polluted": True},
    }
    response = client.post("/library/import-json", json={"payload": payload})
    assert response.status_code == 200
    summary = response.json()
    assert summary["tracks_created"] == 1
    # The bare string is discarded before counting; the two id-less dicts count as skipped.
    assert summary["tracks_skipped"] == 2
    with SessionLocal() as session:
        track = session.scalar(select(Track).where(Track.song_id == "hostile_ok"))
        assert track.title == "Untitled"
        assert track.artist is None
        assert track.manual_multiplier == 1.0
        assert track.clip_start_seconds is None
        assert not track.assets
        assert [link.tag.name for link in track.cooldown_tags] == ["ok-tag"]
        assert not track.embeds  # 500-char id is not a valid provider id
        # The 999-star landed clamped to the same ceiling the live rating path enforces.
        values = [rating.value for rating in track.ratings if rating.value is not None]
        assert values == [5.0]


def test_import_body_size_cap_refuses_oversized_declarations() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/library/import-json",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(65 * 1024 * 1024),
        },
    )
    assert response.status_code == 413
