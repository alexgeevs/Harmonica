from __future__ import annotations

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


def test_rating_change_appends_one_history_sample() -> None:
    with TestClient(create_app()) as client:
        track_id = _make_track(client, "hist_change")

        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 4}})
        assert [s.value for s in _samples(track_id)] == [4.0]

        # Re-saving the SAME value (e.g. the track editor saving all fields) adds nothing.
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 4}})
        assert [s.value for s in _samples(track_id)] == [4.0]

        # A genuine change appends a new sample.
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": 2}})
        assert [s.value for s in _samples(track_id)] == [4.0, 2.0]

        # Clearing the rating records a NULL retract marker.
        client.patch(f"/tracks/{track_id}", json={"ratings": {"overall": None}})
        assert [s.value for s in _samples(track_id)] == [4.0, 2.0, None]


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
