from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
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
    # Optional non-destructive trim window (seconds) to skip YouTube intros/outros.
    clip_start_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    clip_end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # When true, play the audio track only and show artwork instead of the video.
    audio_only: Mapped[bool] = mapped_column(Boolean, default=False)
    # Marks the original rendition within a sub_group (cover set) for the cover prior.
    is_original_rendition: Mapped[bool] = mapped_column(Boolean, default=False)
    # User-tagged favourite. Inert by default; only matters when favourite_pacing_enabled.
    favourite: Mapped[bool] = mapped_column(Boolean, default=False)
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


class RatingSample(Base):
    """Append-only history of every rating action. ``TrackRating.value`` stays the raw
    latest star (for display/badge/export); the algorithm recomputes a normalised
    effective value from these samples each generation (winsorise + shrink toward the
    library mean, mood-corrected). NULL value = an explicit clear/retract marker.
    See docs/planning/rating-normalization-and-covers.md."""

    __tablename__ = "rating_samples"
    __table_args__ = (
        Index("ix_rating_samples_factor_track_created", "factor_id", "track_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    factor_id: Mapped[int] = mapped_column(
        ForeignKey("rating_factors.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..5, or NULL = cleared
    source: Mapped[str] = mapped_column(String(16), default="user")  # 'user' | 'import'
    # Owning user profile (device config). NULL = legacy/global single-user data.
    owner_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Client "sitting" id used by session-mood correction (Phase B); may be null.
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("playlist_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class CoverComparison(Base):
    """Append-only raw log of A/B cover verdicts ("which rendition is better?"). Bradley-Terry
    strengths are always recomputed from these rows, never stored as a running online value, so the
    fit is order-independent and a bad verdict can be deleted and the ranking recomputed cleanly.
    See docs/planning/rating-normalization-and-covers.md (Phase D)."""

    __tablename__ = "cover_comparisons"
    __table_args__ = (Index("ix_cover_comparisons_set_created", "sub_group", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sub_group: Mapped[str] = mapped_column(String(255), index=True)
    # Owning user profile (device config). NULL = legacy/global single-user data.
    owner_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    track_a_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    track_b_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    # NULL winner = "about the same" (a tie), which Bradley-Terry handles as half-credit each side.
    winner_track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True
    )
    pct_a: Mapped[float | None] = mapped_column(Float, nullable=True)  # %-through at verdict
    pct_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("playlist_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class CoverRenditionState(Base):
    """Cache of a rendition's Bradley-Terry log-strength (mean ~0 within its set) so the cover pick
    doesn't refit per slot. Refreshed whenever a verdict lands. Never displayed as an absolute
    star — performance is purely *relative* within the cover set."""

    __tablename__ = "cover_rendition_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), unique=True, index=True
    )
    sub_group: Mapped[str] = mapped_column(String(255), index=True)
    bt_strength: Mapped[float] = mapped_column(Float, default=0.0)
    comparison_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class CoverSetState(Base):
    """Per-set A/B lifecycle flag (Phase E uses it to start/stop prompting; Phase D just keeps the
    running comparison total)."""

    __tablename__ = "cover_set_state"

    sub_group: Mapped[str] = mapped_column(String(255), primary_key=True)
    comparison_phase: Mapped[str] = mapped_column(String(16), default="stars")
    total_comparisons: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class UserCoverSetState(Base):
    """Per-user A/B lifecycle for a cover set. The global ``CoverSetState`` (sub_group is its PK)
    and ``CoverRenditionState`` (track_id is unique) can't hold per-owner rows, so an owned profile
    persists only its set phase here; its rendition strengths are recomputed in-memory from its own
    owner-scoped ``CoverComparison`` verdicts (BT is always refit from the raw log anyway)."""

    __tablename__ = "user_cover_set_state"
    __table_args__ = (
        UniqueConstraint("owner_config_id", "sub_group", name="uq_user_cover_set"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_config_id: Mapped[int] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), index=True
    )
    sub_group: Mapped[str] = mapped_column(String(255), index=True)
    comparison_phase: Mapped[str] = mapped_column(String(16), default="stars")
    total_comparisons: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class PlaylistRun(Base):
    __tablename__ = "playlist_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seed: Mapped[str | None] = mapped_column(String(120), nullable=True)
    length: Mapped[int] = mapped_column(Integer)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    # Owning user profile (device config). NULL = legacy/global single-user data.
    owner_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), nullable=True, index=True
    )
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


class DeviceConfig(Base):
    """A named, passphrase-protected device profile: a settings snapshot plus the
    exact set of songs that device should see. Lets a device re-claim its setup by
    passphrase after its LAN IP rotates. See docs/planning/multi-device-architecture.md."""

    __tablename__ = "device_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    passphrase_hash: Mapped[str] = mapped_column(String(255))
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    tracks: Mapped[list[DeviceConfigTrack]] = relationship(
        back_populates="config", cascade="all, delete-orphan"
    )


class DeviceConfigTrack(Base):
    __tablename__ = "device_config_tracks"
    __table_args__ = (UniqueConstraint("config_id", "track_id", name="uq_config_track"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)

    config: Mapped[DeviceConfig] = relationship(back_populates="tracks")


class PlaybackEvent(Base):
    __tablename__ = "playback_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    # Owning user profile (device config). NULL = legacy/global single-user data.
    owner_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    media_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    playlist_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("playlist_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Hearing-health telemetry (normalized 0..1; see docs/planning/schema-proposal.md).
    avg_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_gain: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )

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


def ensure_additive_track_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    additions = {
        "clip_start_seconds": "ALTER TABLE tracks ADD COLUMN clip_start_seconds FLOAT",
        "clip_end_seconds": "ALTER TABLE tracks ADD COLUMN clip_end_seconds FLOAT",
        "audio_only": "ALTER TABLE tracks ADD COLUMN audio_only BOOLEAN DEFAULT 0",
        "is_original_rendition": (
            "ALTER TABLE tracks ADD COLUMN is_original_rendition BOOLEAN DEFAULT 0"
        ),
        "favourite": "ALTER TABLE tracks ADD COLUMN favourite BOOLEAN DEFAULT 0",
    }
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tracks)").all()
        }
        for name, statement in additions.items():
            if name not in columns:
                connection.exec_driver_sql(statement)


def backfill_rating_samples(engine: Engine) -> None:
    """One-time, idempotent: seed ``rating_samples`` from existing ``TrackRating`` rows so a
    pre-existing library becomes history-capable. Each becomes a single ``source='import'``
    sample (n=1), so normalisation correctly stays inert until songs are re-rated. No-op once
    any sample exists."""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(RatingSample)):
            return
        rows = session.execute(
            select(TrackRating.track_id, TrackRating.factor_id, TrackRating.value).where(
                TrackRating.value.is_not(None)
            )
        ).all()
        if not rows:
            return
        for track_id, factor_id, value in rows:
            session.add(
                RatingSample(
                    track_id=track_id, factor_id=factor_id, value=value, source="import"
                )
            )
        session.commit()


def ensure_additive_playback_event_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    additions = {
        "avg_level": "ALTER TABLE playback_events ADD COLUMN avg_level FLOAT",
        "peak_level": "ALTER TABLE playback_events ADD COLUMN peak_level FLOAT",
        "output_gain": "ALTER TABLE playback_events ADD COLUMN output_gain FLOAT",
    }
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(playback_events)").all()
        }
        for name, statement in additions.items():
            if name not in columns:
                connection.exec_driver_sql(statement)


def ensure_additive_owner_columns(engine: Engine) -> None:
    """Add the per-user ``owner_config_id`` column to the listening tables of a pre-existing DB.
    NULL on every existing row = legacy/global single-user data (the multi-tenant scoping treats a
    request with no owner as "see everything", so old databases keep behaving exactly as before)."""
    if engine.dialect.name != "sqlite":
        return
    tables = ("playback_events", "playlist_runs", "rating_samples", "cover_comparisons")
    with engine.begin() as connection:
        for table in tables:
            columns = {
                row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})").all()
            }
            if "owner_config_id" not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN owner_config_id INTEGER"
                )
