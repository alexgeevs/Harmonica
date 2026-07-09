from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session as OrmSession

from harmonica import models
from harmonica.api import create_app
from harmonica.db import Base, SessionLocal
from harmonica.models import RatingSample, Track


def _make_track(client: TestClient, song_id: str) -> int:
    with SessionLocal() as session:
        track = Track(song_id=song_id, title=f"History {song_id}")
        session.add(track)
        session.commit()
        return track.id


def _samples(track_id: int, factor_key: str = "overall") -> list[RatingSample]:
    with SessionLocal() as session:
        from harmonica.models import RatingFactor

        factor = session.scalar(select(RatingFactor).where(RatingFactor.key == factor_key))
        return list(
            session.scalars(
                select(RatingSample)
                .where(RatingSample.track_id == track_id, RatingSample.factor_id == factor.id)
                .order_by(RatingSample.id)
            )
        )


def _backdate_latest_sample(track_id: int, minutes: int) -> None:
    """Age the newest sample past the correction window, simulating a later listen."""
    with SessionLocal() as session:
        sample = session.scalars(
            select(RatingSample)
            .where(RatingSample.track_id == track_id)
            .order_by(RatingSample.id.desc())
        ).first()
        sample.created_at = sample.created_at - timedelta(minutes=minutes)
        session.commit()


def test_quick_rerate_revises_instead_of_appending() -> None:
    with TestClient(create_app()) as client:
        track_id = _make_track(client, "hist_change")

        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 4}})
        assert [s.value for s in _samples(track_id)] == [4.0]

        # Re-saving the SAME value (e.g. the track editor saving all fields) adds nothing.
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 4}})
        assert [s.value for s in _samples(track_id)] == [4.0]

        # A different value straight away is a correction of the same listen: the last
        # mark is revised in place, so one listen never counts twice.
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 2}})
        assert [s.value for s in _samples(track_id)] == [2.0]

        # A rating well after the last one is a new data point and appends.
        _backdate_latest_sample(track_id, minutes=30)
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 5}})
        assert [s.value for s in _samples(track_id)] == [2.0, 5.0]

        # Clearing shortly after retracts the fresh mark in place.
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": None}})
        assert [s.value for s in _samples(track_id)] == [2.0, None]


def test_displayed_rating_is_running_average() -> None:
    with TestClient(create_app()) as client:
        track_id = _make_track(client, "avg_display")
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 4}})
        assert client.get(f"/tracks/{track_id}").json()["ratings"]["overall"] == 4.0
        # The shown value is the AVERAGE of past listens' ratings, not the latest mark.
        _backdate_latest_sample(track_id, minutes=30)
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 2}})
        assert client.get(f"/tracks/{track_id}").json()["ratings"]["overall"] == 3.0
        # Clearing resets the series (unrated).
        _backdate_latest_sample(track_id, minutes=30)
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": None}})
        assert "overall" not in client.get(f"/tracks/{track_id}").json()["ratings"]


def test_is_original_rendition_roundtrips() -> None:
    with TestClient(create_app()) as client:
        track_id = _make_track(client, "orig_flag")
        assert client.get(f"/tracks/{track_id}").json()["is_original_rendition"] is False
        updated = client.patch(f"/tracks/{track_id}", json={"is_original_rendition": True})
        assert updated.json()["is_original_rendition"] is True


def test_backfill_rating_samples_seeds_history_idempotently() -> None:
    # Isolated in-memory engine so we control the empty-history precondition.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with OrmSession(engine) as session:
        factor = models.RatingFactor(key="overall", label="Overall")
        track = models.Track(song_id="bf1", title="Backfill")
        session.add_all([factor, track])
        session.commit()
        session.add(models.TrackRating(track_id=track.id, factor_id=factor.id, value=3.0))
        session.commit()

    models.backfill_rating_samples(engine)
    with OrmSession(engine) as session:
        rows = list(session.scalars(select(RatingSample)))
        assert len(rows) == 1
        assert rows[0].value == 3.0 and rows[0].source == "import"

    # Idempotent: a second run is a no-op.
    models.backfill_rating_samples(engine)
    with OrmSession(engine) as session:
        assert session.scalar(select(func.count()).select_from(RatingSample)) == 1
