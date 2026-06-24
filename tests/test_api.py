from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from harmonica.api import create_app
from harmonica.db import SessionLocal
from harmonica.models import Track


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
