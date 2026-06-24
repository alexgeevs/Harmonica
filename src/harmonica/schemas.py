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

