from __future__ import annotations

from sqlalchemy import select

from harmonica.config import Settings
from harmonica.cover_ranking import next_pair, record_verdict
from harmonica.db import SessionLocal, init_db
from harmonica.models import CoverSetState, Track


def _make_set(session, sub_group: str, n: int) -> list[int]:
    ids = []
    for i in range(n):
        song_id = f"{sub_group}_r{i}"
        track = session.scalar(select(Track).where(Track.song_id == song_id))
        if track is None:
            track = Track(song_id=song_id, title=f"{sub_group} {i}", sub_group=sub_group)
            session.add(track)
        else:
            track.sub_group = sub_group
        session.commit()
        session.refresh(track)
        ids.append(track.id)
    return ids


def test_next_pair_requires_minimum_covers() -> None:
    init_db()
    settings = Settings()
    with SessionLocal() as session:
        _make_set(session, "rk_small", 2)
        assert next_pair(session, "rk_small", settings) is None  # < 4 covers → not eligible

        _make_set(session, "rk_big", 4)
        pair = next_pair(session, "rk_big", settings)
        assert pair is not None
        assert pair[0] != pair[1]


def test_next_pair_returns_none_once_settled() -> None:
    init_db()
    settings = Settings()
    with SessionLocal() as session:
        ids = _make_set(session, "rk_settle", 4)
        # Drive a decisive, well-separated ranking past the per-cover minimum.
        order = ids
        for _ in range(settings.cover_comparison_min_per_cover + 1):
            for i in range(len(order)):
                for j in range(i + 1, len(order)):
                    record_verdict(session, "rk_settle", order[i], order[j], order[i], settings)
        session.commit()
        state = session.get(CoverSetState, "rk_settle")
        assert state.comparison_phase == "settled"
        assert next_pair(session, "rk_settle", settings) is None


def test_next_pair_prefers_least_compared_uncertain_pair() -> None:
    init_db()
    settings = Settings()
    with SessionLocal() as session:
        ids = _make_set(session, "rk_info", 4)
        # Heavily compare the first three; leave the 4th almost untouched.
        for _ in range(4):
            record_verdict(session, "rk_info", ids[0], ids[1], ids[0], settings)
            record_verdict(session, "rk_info", ids[1], ids[2], ids[1], settings)
            record_verdict(session, "rk_info", ids[0], ids[2], ids[0], settings)
        session.commit()
        pair = next_pair(session, "rk_info", settings)
        assert pair is not None
        # The under-compared 4th rendition should be in the next chosen pair.
        assert ids[3] in pair
