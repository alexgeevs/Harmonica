from __future__ import annotations

from pydantic import BaseModel, Field


class MediaAssetRead(BaseModel):
    id: int
    file_path: str
    asset_type: str
    codec: str | None = None
    container: str | None = None
    source: str | None = None
    source_quality: str | None = None
    is_lossless: bool | None = None
    checksum: str | None = None
    browser_supported: bool


class EmbedRead(BaseModel):
    id: int
    provider: str
    external_id: str
    url: str | None = None
    start_seconds: float | None = None


class EmbedWrite(BaseModel):
    # Either a full provider+id, or just a url that the server parses into one.
    provider: str | None = None
    external_id: str | None = None
    url: str | None = None
    start_seconds: float | None = None


class GroupRead(BaseModel):
    id: int
    name: str
    group_type: str
    manual_multiplier: float
    rating_multiplier: float


class TrackGroupRead(BaseModel):
    id: int
    name: str
    group_type: str
    share: float | None = None


class RatingFactorRead(BaseModel):
    id: int
    key: str
    label: str
    weight: float
    applies_to_lyrics: bool
    applies_to_instrumental: bool
    applies_to_variants_only: bool
    enabled: bool


class TrackRead(BaseModel):
    id: int
    song_id: str
    title: str
    artist: str | None = None
    album: str | None = None
    has_lyrics: bool
    sub_group: str | None = None
    manual_multiplier: float
    clip_start_seconds: float | None = None
    clip_end_seconds: float | None = None
    audio_only: bool = False
    is_original_rendition: bool = False
    favourite: bool = False
    assets: list[MediaAssetRead] = Field(default_factory=list)
    embeds: list[EmbedRead] = Field(default_factory=list)
    groups: list[TrackGroupRead] = Field(default_factory=list)
    cooldown_tags: list[str] = Field(default_factory=list)
    ratings: dict[str, float | None] = Field(default_factory=dict)


class TrackGroupWrite(BaseModel):
    name: str
    group_type: str = "other"
    share: float | None = None


class TrackUpdate(BaseModel):
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    has_lyrics: bool | None = None
    sub_group: str | None = None
    manual_multiplier: float | None = None
    clip_start_seconds: float | None = None
    clip_end_seconds: float | None = None
    audio_only: bool | None = None
    is_original_rendition: bool | None = None
    favourite: bool | None = None
    embeds: list[EmbedWrite] | None = None
    groups: list[TrackGroupWrite] | None = None
    cooldown_tags: list[str] | None = None
    ratings: dict[str, float | None] | None = None
    # Optional client "sitting" id, threaded onto rating samples for session-mood (Phase B).
    rating_session_id: str | None = None


class ScanRequest(BaseModel):
    library: str
    create_tag_groups: bool = True


class ScanResponse(BaseModel):
    scanned: int
    created_tracks: int
    created_assets: int
    skipped_existing_assets: int


class QueueGenerateRequest(BaseModel):
    length: int = Field(default=100, ge=1, le=1000)
    seed: str | None = None
    explain: bool = True
    ui_active: bool = False
    config_id: int | None = None


class QueueItemRead(BaseModel):
    position: int
    track: TrackRead
    media_asset_id: int | None = None
    media_url: str | None = None
    score: float
    explanation: dict


class QueueRunRead(BaseModel):
    id: int
    seed: str | None = None
    length: int
    items: list[QueueItemRead]


class PlaylistRunSummary(BaseModel):
    id: int
    name: str | None = None
    seed: str | None = None
    length: int
    item_count: int
    created_at: str
    preview_titles: list[str] = Field(default_factory=list)


class PlaylistRunRename(BaseModel):
    name: str | None = None


class SettingControlRead(BaseModel):
    key: str
    label: str
    description: str
    value_type: str
    control: str
    default: int | float | bool
    minimum: int | float | None = None
    maximum: int | float | None = None
    step: int | float | None = None
    unit: str | None = None
    value: int | float | bool


class SettingsRead(BaseModel):
    beta: float
    group_cooldown_floor: float
    sub_group_cooldown_floor: float
    song_rating_min_multiplier: float
    song_rating_max_multiplier: float
    enable_group_rating_multiplier: bool
    home: str
    host: str
    port: int
    default_playlist_length: int
    group_rating_min_multiplier: float
    group_rating_max_multiplier: float
    history_influence_enabled: bool
    skip_penalty_strength: float
    cold_start_enabled: bool
    cold_start_unrated_boost: float
    visual_priority_enabled: bool
    visual_priority_multiplier: float
    group_clustering_bias: float
    avoid_consecutive_compressed: bool
    compressed_break_reminder: bool
    loudness_warning_enabled: bool
    loudness_warning_level: float
    rating_normalization_enabled: bool
    rating_outlier_sd: float
    rating_session_mood_correction: bool
    rating_session_min_songs: int
    rating_coverage_ready_fraction: float
    rating_calibration_enabled: bool
    satiation_enabled: bool
    satiation_strength: float
    satiation_window_days: float
    rediscovery_enabled: bool
    rediscovery_strength: float
    rediscovery_halflife_days: float
    favourite_pacing_enabled: bool
    favourite_pacing_strength: float
    youtube_embed_enabled: bool
    spotify_enabled: bool
    why_show_math: bool
    cover_two_level_enabled: bool
    cover_count_log_base: float
    cover_original_bonus: float
    controls: list[SettingControlRead]


class SettingsUpdate(BaseModel):
    values: dict[str, int | float | bool]


class SpotifyTrackRead(BaseModel):
    name: str
    artists: list[str]
    album: str | None = None
    duration_ms: int | None = None
    spotify_id: str | None = None
    url: str | None = None


class SpotifyPlaylistRead(BaseModel):
    id: str
    name: str | None = None
    tracks: list[SpotifyTrackRead]
    truncated: bool = False


class CoverVerdictCreate(BaseModel):
    """A user's A/B verdict on which rendition of a song is better."""

    sub_group: str
    track_a_id: int
    track_b_id: int
    winner_track_id: int | None = None  # null = "about the same"
    pct_a: float | None = None
    pct_b: float | None = None
    session_id: str | None = None
    run_id: int | None = None


class CoverRenditionRead(BaseModel):
    track_id: int
    sub_group: str
    bt_strength: float
    comparison_count: int


class CoverComparisonPair(BaseModel):
    """The next A/B pair to play back-to-back for a head-to-head, as two ready-to-queue items."""

    sub_group: str
    a: QueueItemRead
    b: QueueItemRead


class CoverSetRead(BaseModel):
    """The post-verdict state of a cover set: its lifecycle phase and each rendition's relative
    Bradley-Terry strength (mean ~0; higher = preferred)."""

    sub_group: str
    comparison_phase: str
    total_comparisons: int
    renditions: list[CoverRenditionRead]


class DeviceConfigCreate(BaseModel):
    name: str
    passphrase: str
    settings: dict[str, int | float | bool] = Field(default_factory=dict)
    track_ids: list[int] = Field(default_factory=list)


class DeviceConfigUpdate(BaseModel):
    passphrase: str
    settings: dict[str, int | float | bool] | None = None
    track_ids: list[int] | None = None


class DeviceConfigClaim(BaseModel):
    name: str
    passphrase: str


class DeviceConfigSummary(BaseModel):
    id: int
    name: str
    track_count: int
    created_at: str


class DeviceConfigDetail(BaseModel):
    id: int
    name: str
    settings: dict[str, int | float | bool] = Field(default_factory=dict)
    included_track_ids: list[int] = Field(default_factory=list)
    # Signed bearer token proving this profile's identity; sent back on create/claim only (the
    # client stores it and presents it as `Authorization: Bearer` so its data stays scoped).
    token: str | None = None


class PlaybackEventCreate(BaseModel):
    event_type: str
    track_id: int
    media_asset_id: int | None = None
    playlist_run_id: int | None = None
    queue_position: int | None = None
    progress_seconds: float | None = None
    duration_seconds: float | None = None
    avg_level: float | None = None
    peak_level: float | None = None
    output_gain: float | None = None


class PlaybackEventRead(BaseModel):
    id: int
    event_type: str
    track_id: int
    media_asset_id: int | None = None
    playlist_run_id: int | None = None
    queue_position: int | None = None
    progress_seconds: float | None = None
    duration_seconds: float | None = None
    avg_level: float | None = None
    peak_level: float | None = None
    output_gain: float | None = None
    created_at: str


class StatsSummaryRead(BaseModel):
    track_count: int
    rated_track_count: int
    unrated_track_count: int
    video_track_count: int
    group_count: int
    playback_event_count: int
    completed_count: int
    skipped_count: int
    early_skip_count: int
    partial_skip_count: int


class LibraryImportRequest(BaseModel):
    payload: dict
