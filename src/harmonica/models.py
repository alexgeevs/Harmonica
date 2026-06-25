from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column, relationship

from harmonica.db import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    song_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    artist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    album: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_lyrics: Mapped[bool] = mapped_column(Boolean, default=True)
    sub_group: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    manual_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    assets: Mapped[list[MediaAsset]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    ratings: Mapped[list[TrackRating]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    cooldown_tags: Mapped[list[TrackCooldownTag]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(Text, unique=True)
    asset_type: Mapped[str] = mapped_column(String(32), default="audio")
    codec: Mapped[str | None] = mapped_column(String(120), nullable=True)
    container: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_quality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_lossless: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    browser_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    track: Mapped[Track] = relationship(back_populates="assets")


class WeightGroup(Base):
    __tablename__ = "weight_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    group_type: Mapped[str] = mapped_column(String(80), default="other")
    manual_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    rating_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("track_id", "group_id", name="uq_track_group"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("weight_groups.id", ondelete="CASCADE"), index=True
    )
    share: Mapped[float | None] = mapped_column(Float, nullable=True)

    track: Mapped[Track] = relationship(back_populates="memberships")
    group: Mapped[WeightGroup] = relationship(back_populates="memberships")


class CooldownTag(Base):
    __tablename__ = "cooldown_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    tracks: Mapped[list[TrackCooldownTag]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class TrackCooldownTag(Base):
    __tablename__ = "track_cooldown_tags"
    __table_args__ = (UniqueConstraint("track_id", "tag_id", name="uq_track_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("cooldown_tags.id", ondelete="CASCADE"), index=True
    )

    track: Mapped[Track] = relationship(back_populates="cooldown_tags")
    tag: Mapped[CooldownTag] = relationship(back_populates="tracks")


class RatingFactor(Base):
    __tablename__ = "rating_factors"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    applies_to_lyrics: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_instrumental: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_variants_only: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    ratings: Mapped[list[TrackRating]] = relationship(
        back_populates="factor", cascade="all, delete-orphan"
    )


class TrackRating(Base):
    __tablename__ = "track_ratings"
    __table_args__ = (UniqueConstraint("track_id", "factor_id", name="uq_track_rating_factor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    factor_id: Mapped[int] = mapped_column(
        ForeignKey("rating_factors.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    track: Mapped[Track] = relationship(back_populates="ratings")
    factor: Mapped[RatingFactor] = relationship(back_populates="ratings")


class PlaylistRun(Base):
    __tablename__ = "playlist_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seed: Mapped[str | None] = mapped_column(String(120), nullable=True)
    length: Mapped[int] = mapped_column(Integer)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    items: Mapped[list[PlaylistItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="PlaylistItem.position"
    )


class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_run_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("playlist_runs.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    media_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    explanation_json: Mapped[str] = mapped_column(Text, default="{}")

    run: Mapped[PlaylistRun] = relationship(back_populates="items")
    track: Mapped[Track] = relationship()
    media_asset: Mapped[MediaAsset | None] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class PlaybackEvent(Base):
    __tablename__ = "playback_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    media_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    playlist_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("playlist_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    track: Mapped[Track] = relationship()
    media_asset: Mapped[MediaAsset | None] = relationship()
    playlist_run: Mapped[PlaylistRun | None] = relationship()


def ensure_additive_playlist_run_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(playlist_runs)").all()
        }
        if "name" not in columns:
            connection.exec_driver_sql("ALTER TABLE playlist_runs ADD COLUMN name VARCHAR(255)")
