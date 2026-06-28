from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from harmonica.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings | None = None):
    resolved = settings or get_settings()
    connect_args = {"check_same_thread": False} if resolved.db_url.startswith("sqlite") else {}
    return create_engine(resolved.db_url, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    from harmonica import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    # Additive upgrades for pre-existing DBs. Wired here (not only in create_app) so the
    # CLI and seed scripts — which call init_db() but not the API factory — also get them.
    models.ensure_additive_playlist_run_columns(engine)
    models.ensure_additive_track_columns(engine)
    models.ensure_additive_playback_event_columns(engine)
    models.backfill_rating_samples(engine)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

