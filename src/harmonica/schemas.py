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
    assets: list[MediaAssetRead] = Field(default_factory=list)
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
    groups: list[TrackGroupWrite] | None = None
    cooldown_tags: list[str] | None = None
    ratings: dict[str, float | None] | None = None


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
    controls: list[SettingControlRead]


class SettingsUpdate(BaseModel):
    values: dict[str, int | float | bool]


class PlaybackEventCreate(BaseModel):
    event_type: str
    track_id: int
    media_asset_id: int | None = None
    playlist_run_id: int | None = None
    queue_position: int | None = None
    progress_seconds: float | None = None
    duration_seconds: float | None = None


class PlaybackEventRead(BaseModel):
    id: int
    event_type: str
    track_id: int
    media_asset_id: int | None = None
    playlist_run_id: int | None = None
    queue_position: int | None = None
    progress_seconds: float | None = None
    duration_seconds: float | None = None
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
