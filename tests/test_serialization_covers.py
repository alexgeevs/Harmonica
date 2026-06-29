from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from harmonica.config import Settings
from harmonica.db import Base
from harmonica.models import (
    CoverComparison,
    CoverRenditionState,
    CoverSetState,
    RatingFactor,
    RatingSample,
    Track,
)
from harmonica.serialization import export_library_payload, import_library_payload


def _fresh_session(tmp_path, name: str) -> Session:
    import harmonica.models  # noqa: F401 — register tables

    engine = create_engine(f"sqlite:///{tmp_path / name}.db")
    Base.metadata.create_all(engine)
    return Session(bind=engine, expire_on_commit=False)


def _seed_source(session: Session) -> None:
    overall = RatingFactor(key="overall", label="Overall")
    session.add(overall)
    session.flush()
    ids = []
    for i in range(4):
        track = Track(
            song_id=f"q{i}",
            title=f"Quad {i}",
            sub_group="quad",
            is_original_rendition=(i == 0),
        )
        session.add(track)
        session.flush()
        ids.append(track.id)
        # Some rating history for the first track.
        if i == 0:
            for value in (4.0, 5.0):
                session.add(RatingSample(track_id=track.id, factor_id=overall.id, value=value))
    # A decisive set of verdicts: track 0 beats the rest.
    for j in range(1, 4):
        for _ in range(2):
            session.add(
                CoverComparison(
                    sub_group="quad",
                    track_a_id=ids[0],
                    track_b_id=ids[j],
                    winner_track_id=ids[0],
                )
            )
    session.commit()


def test_history_and_verdicts_survive_export_import(tmp_path) -> None:
    source = _fresh_session(tmp_path, "src")
    _seed_source(source)
    payload = export_library_payload(source)

    assert len(payload["rating_samples"]) == 2
    assert len(payload["cover_comparisons"]) == 6
    assert any(t["is_original_rendition"] for t in payload["tracks"])

    dest = _fresh_session(tmp_path, "dst")
    import_library_payload(dest, payload, Settings())

    # Raw history transferred, keyed by song_id (local ids differ between the two DBs).
    assert dest.scalar(select(func.count(RatingSample.id))) == 2
    assert dest.scalar(select(func.count(CoverComparison.id))) == 6
    original = dest.scalar(select(Track).where(Track.song_id == "q0"))
    assert original.is_original_rendition is True

    # The Bradley-Terry cache is RECOMPUTED on import, not trusted from the export.
    states = {
        row.track_id: row
        for row in dest.scalars(
            select(CoverRenditionState).where(CoverRenditionState.sub_group == "quad")
        )
    }
    assert states, "rendition strengths should be rebuilt on import"
    winner = dest.scalar(select(Track).where(Track.song_id == "q0"))
    loser = dest.scalar(select(Track).where(Track.song_id == "q1"))
    assert states[winner.id].bt_strength > states[loser.id].bt_strength
    set_state = dest.get(CoverSetState, "quad")
    assert set_state is not None and set_state.total_comparisons == 6


def test_reimport_is_idempotent(tmp_path) -> None:
    source = _fresh_session(tmp_path, "src2")
    _seed_source(source)
    payload = export_library_payload(source)

    dest = _fresh_session(tmp_path, "dst2")
    import_library_payload(dest, payload, Settings())
    import_library_payload(dest, payload, Settings())  # second import must not duplicate

    assert dest.scalar(select(func.count(RatingSample.id))) == 2
    assert dest.scalar(select(func.count(CoverComparison.id))) == 6
