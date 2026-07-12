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
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

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
    embeds: Mapped[list[Embed]] = relationship(
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


class Embed(Base):
    """An optional third-party player source for a song (e.g. a YouTube video id). Playback uses the
    provider's OFFICIAL embedded player; Harmonica never downloads, scrapes, strips ads from, or
    extracts audio from embedded content. Inert unless the user opts into embeds."""

    __tablename__ = "embeds"
    __table_args__ = (
        UniqueConstraint("track_id", "provider", "external_id", name="uq_embed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Official start offset (the provider's supported start=/t= parameter) for trimming an intro.
    start_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    track: Mapped[Track] = relationship(back_populates="embeds")


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


FAVOURITE_TAG_NAME = "Favourite"
IGNORED_TAG_NAME = "Ignored"
SYSTEM_TAG_NAMES = (FAVOURITE_TAG_NAME, IGNORED_TAG_NAME)
DEFAULT_CUSTOM_TAG_NAMES = ("Fun", "Focused")


class Tag(Base):
    """A user-facing organisational label on tracks. ``kind`` separates the fixed system tags
    (Favourite, Ignored) from user-managed custom tags. ``shared`` shows every scope's
    assignments to everyone (each scope still owns its own rows, so one profile's removals
    never touch another's). ``affects_algorithm`` opts a tag into the light pacing layer
    (cosmetic otherwise). Distinct from ``CooldownTag``, which is the scanner's grouping
    shorthand, not a user tag."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="custom")  # 'system' | 'custom'
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    affects_algorithm: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class TrackTag(Base):
    """One tag assignment. ``owner_config_id`` scopes it: a profile's private opinion, or NULL for
    local mode and for every assignment of a shared tag. No UNIQUE constraint because SQLite
    treats NULLs as distinct inside one; uniqueness of (track, tag, owner) is enforced by the
    idempotent upserts in the API and import layers."""

    __tablename__ = "track_tags"
    __table_args__ = (Index("ix_track_tags_tag_owner", "tag_id", "owner_config_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), index=True)
    owner_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    tag: Mapped[Tag] = relationship()


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
    # Per-profile favourite tag. A favourite is one user's private opinion of a shared song, so it
    # lives on the per-user link, not on the shared Track (legacy/local mode uses Track.favourite).
    favourite: Mapped[bool] = mapped_column(Boolean, default=False)

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


def ensure_additive_device_config_track_columns(engine: Engine) -> None:
    """Add the per-profile ``favourite`` column to the profile-track link on a pre-existing DB."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(device_config_tracks)").all()
        }
        if "favourite" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE device_config_tracks ADD COLUMN favourite BOOLEAN DEFAULT 0"
            )


def favourite_track_ids(session: Session, owner_config_id: int) -> set[int]:
    """The track ids one profile has tagged as favourites (its private per-user opinion)."""
    rows = session.scalars(
        select(DeviceConfigTrack.track_id).where(
            DeviceConfigTrack.config_id == owner_config_id,
            DeviceConfigTrack.favourite.is_(True),
        )
    )
    return set(rows)


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


def seed_and_backfill_tags(engine: Engine) -> None:
    """One-time, idempotent: create the system tags (Favourite, Ignored) and the starter custom
    tags, then copy the existing favourite booleans into tag assignments (``Track.favourite`` →
    an unowned row; ``DeviceConfigTrack.favourite`` → a row owned by that profile). No-op once
    any tag exists."""
    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(Tag)):
            return
        by_name: dict[str, Tag] = {}
        for name in SYSTEM_TAG_NAMES:
            tag = Tag(name=name, kind="system")
            session.add(tag)
            by_name[name] = tag
        for name in DEFAULT_CUSTOM_TAG_NAMES:
            session.add(Tag(name=name, kind="custom"))
        session.flush()
        favourite = by_name[FAVOURITE_TAG_NAME]
        for track_id in session.scalars(select(Track.id).where(Track.favourite.is_(True))):
            session.add(TrackTag(track_id=track_id, tag_id=favourite.id, owner_config_id=None))
        rows = session.execute(
            select(DeviceConfigTrack.track_id, DeviceConfigTrack.config_id).where(
                DeviceConfigTrack.favourite.is_(True)
            )
        ).all()
        for track_id, config_id in rows:
            session.add(
                TrackTag(track_id=track_id, tag_id=favourite.id, owner_config_id=config_id)
            )
        session.commit()


def visible_tag_rows(session: Session, owner_config_id: int | None) -> list[tuple[int, Tag]]:
    """Every (track_id, Tag) assignment visible to one scope. A shared tag's assignments count
    for everyone; a per-profile tag counts only rows stamped with the requesting owner (NULL in
    local mode)."""
    rows = session.execute(
        select(TrackTag.track_id, TrackTag.owner_config_id, Tag).join(
            Tag, TrackTag.tag_id == Tag.id
        )
    ).all()
    return [
        (track_id, tag)
        for track_id, row_owner, tag in rows
        if tag.shared or row_owner == owner_config_id
    ]


def visible_tags_by_track(session: Session, owner_config_id: int | None) -> dict[int, list[str]]:
    """Tag names per track for one scope, sorted for stable API output."""
    result: dict[int, list[str]] = {}
    for track_id, tag in visible_tag_rows(session, owner_config_id):
        names = result.setdefault(track_id, [])
        if tag.name not in names:
            names.append(tag.name)
    for names in result.values():
        names.sort()
    return result


def tag_track_ids(
    session: Session, tag_names: list[str], owner_config_id: int | None
) -> set[int]:
    """Union of track ids carrying ANY of the named tags, in one scope."""
    wanted = set(tag_names)
    return {
        track_id
        for track_id, tag in visible_tag_rows(session, owner_config_id)
        if tag.name in wanted
    }


def algorithm_tag_inputs(
    session: Session, owner_config_id: int | None
) -> tuple[set[int], dict[int, frozenset[str]]]:
    """What queue generation needs from the tags in one scope: the ignored track ids (always
    excluded from the candidate pool) and each track's algorithm-active tag names (fed to the
    light pacing layer). Favourite stays out of both — its algorithm effect is favourite pacing,
    driven by the existing boolean input."""
    ignored: set[int] = set()
    active: dict[int, set[str]] = {}
    for track_id, tag in visible_tag_rows(session, owner_config_id):
        if tag.name == IGNORED_TAG_NAME:
            ignored.add(track_id)
        elif tag.affects_algorithm:
            active.setdefault(track_id, set()).add(tag.name)
    return ignored, {track_id: frozenset(names) for track_id, names in active.items()}


def materialise_shared_assignments(session: Session, tag_id: int) -> None:
    """When a household-shared tag becomes per-profile, nobody may lose it: every song the
    household saw tagged stays tagged in each existing profile and in local mode. Each scope
    then owns its copy independently."""
    rows = session.scalars(select(TrackTag).where(TrackTag.tag_id == tag_id)).all()
    if not rows:
        return
    track_ids = {row.track_id for row in rows}
    existing = {(row.track_id, row.owner_config_id) for row in rows}
    scopes: list[int | None] = [None, *session.scalars(select(DeviceConfig.id))]
    for track_id in track_ids:
        for scope in scopes:
            if (track_id, scope) not in existing:
                session.add(
                    TrackTag(track_id=track_id, tag_id=tag_id, owner_config_id=scope)
                )


def set_favourite_tag(
    session: Session, track_id: int, value: bool, owner_config_id: int | None
) -> None:
    """Keep the Favourite tag row in step with the favourite boolean for one scope (the tag
    tables are the source of truth, but both systems must agree on every write)."""
    tag = session.scalar(select(Tag).where(Tag.name == FAVOURITE_TAG_NAME))
    if tag is None:
        return
    owner_clause = (
        TrackTag.owner_config_id.is_(None)
        if owner_config_id is None
        else TrackTag.owner_config_id == owner_config_id
    )
    row = session.scalar(
        select(TrackTag).where(
            TrackTag.track_id == track_id, TrackTag.tag_id == tag.id, owner_clause
        )
    )
    if value and row is None:
        session.add(TrackTag(track_id=track_id, tag_id=tag.id, owner_config_id=owner_config_id))
    elif not value and row is not None:
        session.delete(row)
