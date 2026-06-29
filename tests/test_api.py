from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from harmonica.api import create_app
from harmonica.db import SessionLocal
from harmonica.models import DeviceConfig, PlaylistItem, PlaylistRun, Track


def test_api_smoke() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["ok"] is True
        factors = client.get("/rating-factors")
        assert factors.status_code == 200
        assert {factor["key"] for factor in factors.json()} >= {"lyrics", "music", "overall"}


def test_settings_can_be_updated() -> None:
    with TestClient(create_app()) as client:
        original = client.get("/settings").json()
        response = client.patch("/settings", json={"values": {"beta": 1.5}})
        assert response.status_code == 200
        assert response.json()["beta"] == 1.5
        assert any(control["key"] == "beta" for control in response.json()["controls"])
        client.patch("/settings", json={"values": {"beta": original["beta"]}})


def test_new_optional_features_default_off_and_toggle() -> None:
    with TestClient(create_app()) as client:
        body = client.get("/settings").json()
        # The maths view and two-level covers are opt-in: present and off by default.
        assert body["why_show_math"] is False
        assert body["cover_two_level_enabled"] is False
        keys = {control["key"] for control in body["controls"]}
        assert {"why_show_math", "cover_two_level_enabled"} <= keys
        # Satiation/rediscovery remain disableable switches.
        assert {"satiation_enabled", "rediscovery_enabled"} <= keys

        toggled = client.patch("/settings", json={"values": {"why_show_math": True}})
        assert toggled.json()["why_show_math"] is True
        client.patch("/settings", json={"values": {"why_show_math": False}})


def test_cover_verdict_records_and_ranks_renditions() -> None:
    with TestClient(create_app()) as client:
        with SessionLocal() as session:
            ids = []
            for suffix in ("a", "b"):
                song_id = f"verdict_set_{suffix}"
                track = session.scalar(select(Track).where(Track.song_id == song_id))
                if track is None:
                    track = Track(
                        song_id=song_id, title=f"Rendition {suffix}", sub_group="verdict_set"
                    )
                    session.add(track)
                else:
                    track.sub_group = "verdict_set"
                session.commit()
                session.refresh(track)
                ids.append(track.id)
            a_id, b_id = ids

        # A is judged better than B three times.
        body = None
        for _ in range(3):
            response = client.post(
                "/cover-verdicts",
                json={
                    "sub_group": "verdict_set",
                    "track_a_id": a_id,
                    "track_b_id": b_id,
                    "winner_track_id": a_id,
                },
            )
            assert response.status_code == 200
            body = response.json()

        assert body["total_comparisons"] == 3
        assert body["comparison_phase"] == "bootstrapping"
        strengths = {r["track_id"]: r["bt_strength"] for r in body["renditions"]}
        assert strengths[a_id] > strengths[b_id]

        # A bogus winner is rejected rather than silently fed to the fit.
        bad = client.post(
            "/cover-verdicts",
            json={
                "sub_group": "verdict_set",
                "track_a_id": a_id,
                "track_b_id": b_id,
                "winner_track_id": 999999,
            },
        )
        assert bad.status_code == 400

        fetched = client.get("/cover-sets/verdict_set").json()
        assert fetched["total_comparisons"] == 3


def test_playback_event_can_be_recorded() -> None:
    with TestClient(create_app()) as client:
        with SessionLocal() as session:
            track = session.scalar(select(Track).where(Track.song_id == "api_playback_test"))
            if track is None:
                track = Track(song_id="api_playback_test", title="API Playback Test")
                session.add(track)
                session.commit()
                session.refresh(track)
            track_id = track.id

        response = client.post(
            "/playback-events",
            json={
                "event_type": "started",
                "track_id": track_id,
                "progress_seconds": 0,
                "duration_seconds": 120,
            },
        )
        assert response.status_code == 200
        assert response.json()["event_type"] == "started"
        assert response.json()["track_id"] == track_id


def test_stats_summary_is_available() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/stats/summary")
        assert response.status_code == 200
        payload = response.json()
        assert "track_count" in payload
        assert "early_skip_count" in payload


def test_library_export_is_agent_friendly_json() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/library/export-json")
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) >= {"rating_factors", "groups", "tracks"}


def test_playlist_runs_can_be_listed_renamed_and_deleted() -> None:
    with TestClient(create_app()) as client:
        with SessionLocal() as session:
            tracks = [
                get_or_create_track(
                    session,
                    song_id=f"api_playlist_summary_{index}",
                    title=f"Queue Preview {index}",
                )
                for index in range(5)
            ]
            older_run = PlaylistRun(
                name=None,
                seed="api-summary-old",
                length=1,
                created_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
            newer_run = PlaylistRun(
                name="Draft queue",
                seed="api-summary-new",
                length=5,
                created_at=datetime(2099, 1, 2, tzinfo=UTC),
            )
            session.add_all([older_run, newer_run])
            session.flush()
            session.add(
                PlaylistItem(
                    run=older_run,
                    track_id=tracks[0].id,
                    position=0,
                    score=1.0,
                )
            )
            for index, track in enumerate(tracks):
                session.add(
                    PlaylistItem(
                        run=newer_run,
                        track_id=track.id,
                        position=index,
                        score=1.0,
                    )
                )
            session.commit()
            older_run_id = older_run.id
            newer_run_id = newer_run.id

        response = client.get("/playlist-runs", params={"limit": 1})
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == newer_run_id
        assert payload[0]["name"] == "Draft queue"
        assert payload[0]["seed"] == "api-summary-new"
        assert payload[0]["length"] == 5
        assert payload[0]["item_count"] == 5
        assert payload[0]["preview_titles"] == [
            "Queue Preview 0",
            "Queue Preview 1",
            "Queue Preview 2",
            "Queue Preview 3",
        ]

        rename = client.patch(f"/playlist-runs/{newer_run_id}", json={"name": "Evening queue"})
        assert rename.status_code == 200
        assert rename.json()["name"] == "Evening queue"

        full_run = client.get(f"/playlist-runs/{newer_run_id}")
        assert full_run.status_code == 200
        assert len(full_run.json()["items"]) == 5

        delete = client.delete(f"/playlist-runs/{newer_run_id}")
        assert delete.status_code == 204
        assert client.get(f"/playlist-runs/{newer_run_id}").status_code == 404
        assert client.delete(f"/playlist-runs/{older_run_id}").status_code == 204


def get_or_create_track(session, song_id: str, title: str) -> Track:
    track = session.scalar(select(Track).where(Track.song_id == song_id))
    if track is None:
        track = Track(song_id=song_id, title=title)
        session.add(track)
        session.flush()
    return track


def test_device_config_claim_and_scoped_generation() -> None:
    with TestClient(create_app()) as client:
        with SessionLocal() as session:
            track = session.scalar(select(Track).where(Track.song_id == "api_config_test"))
            if track is None:
                track = Track(song_id="api_config_test", title="API Config Test")
                session.add(track)
                session.commit()
                session.refresh(track)
            track_id = track.id
            # Idempotent across re-runs against a shared dev DB.
            existing = session.scalar(
                select(DeviceConfig).where(DeviceConfig.name == "api-config-test")
            )
            if existing is not None:
                session.delete(existing)
                session.commit()

        created = client.post(
            "/configs",
            json={
                "name": "api-config-test",
                "passphrase": "green-fox",
                "settings": {"default_playlist_length": 7},
                "track_ids": [track_id],
            },
        )
        assert created.status_code == 200
        config_id = created.json()["id"]
        assert created.json()["included_track_ids"] == [track_id]

        # Listing exposes names but never secrets.
        listed = client.get("/configs").json()
        assert any(c["name"] == "api-config-test" for c in listed)
        assert all("passphrase" not in c and "passphrase_hash" not in c for c in listed)

        # Wrong passphrase is rejected; correct one returns the detail.
        wrong = client.post("/configs/claim", json={"name": "api-config-test", "passphrase": "no"})
        assert wrong.status_code == 401
        claimed = client.post(
            "/configs/claim", json={"name": "api-config-test", "passphrase": "green-fox"}
        )
        assert claimed.status_code == 200
        assert claimed.json()["id"] == config_id

        # Generation scoped to the config only draws from its included songs.
        generated = client.post("/queue/generate", json={"length": 5, "config_id": config_id})
        assert generated.status_code == 200
        track_ids = {item["track"]["id"] for item in generated.json()["items"]}
        assert track_ids <= {track_id}
