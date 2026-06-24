from __future__ import annotations

import json
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from harmonica.bootstrap import ensure_default_rating_factors
from harmonica.config import Settings, get_settings
from harmonica.db import SessionLocal, get_session, init_db
from harmonica.models import (
    CooldownTag,
    GroupMembership,
    MediaAsset,
    PlaybackEvent,
    PlaylistRun,
    RatingFactor,
    Track,
    TrackCooldownTag,
    TrackRating,
    WeightGroup,
)
from harmonica.playlist import generate_and_persist_playlist
from harmonica.scanner import scan_library
from harmonica.schemas import (
    GroupRead,
    PlaybackEventCreate,
    PlaybackEventRead,
    QueueGenerateRequest,
    QueueItemRead,
    QueueRunRead,
    RatingFactorRead,
    ScanRequest,
    ScanResponse,
    SettingsRead,
    SettingsUpdate,
    TrackGroupWrite,
    TrackRead,
    TrackUpdate,
)
from harmonica.settings_store import get_effective_settings, settings_payload, update_setting_values

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def create_app() -> FastAPI:
    init_db()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        with SessionLocal() as session:
            ensure_default_rating_factors(session)
        yield

    app = FastAPI(title="Harmonica", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health(settings: SettingsDep) -> dict[str, Any]:
        return {"ok": True, "app": settings.app_name}

    @app.get("/settings", response_model=SettingsRead)
    def read_settings(session: SessionDep, settings: SettingsDep) -> SettingsRead:
        return SettingsRead(**settings_payload(session, settings))

    @app.patch("/settings", response_model=SettingsRead)
    def update_settings(
        payload: SettingsUpdate,
        session: SessionDep,
        settings: SettingsDep,
    ) -> SettingsRead:
        update_setting_values(session, payload.values, settings)
        return SettingsRead(**settings_payload(session, settings))

    @app.get("/rating-factors", response_model=list[RatingFactorRead])
    def list_rating_factors(session: SessionDep) -> list[RatingFactorRead]:
        ensure_default_rating_factors(session)
        factors = session.scalars(select(RatingFactor).order_by(RatingFactor.id)).all()
        return [rating_factor_to_schema(factor) for factor in factors]

    @app.get("/groups", response_model=list[GroupRead])
    def list_groups(session: SessionDep) -> list[GroupRead]:
        groups = session.scalars(select(WeightGroup).order_by(WeightGroup.name)).all()
        return [group_to_schema(group) for group in groups]

    @app.get("/tracks", response_model=list[TrackRead])
    def list_tracks(session: SessionDep) -> list[TrackRead]:
        query = track_query().order_by(Track.artist, Track.album, Track.title)
        tracks = session.scalars(query).all()
        return [track_to_schema(track) for track in tracks]

    @app.get("/tracks/{track_id}", response_model=TrackRead)
    def read_track(track_id: int, session: SessionDep) -> TrackRead:
        track = session.scalar(track_query().where(Track.id == track_id))
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        return track_to_schema(track)

    @app.patch("/tracks/{track_id}", response_model=TrackRead)
    def update_track(
        track_id: int,
        payload: TrackUpdate,
        session: SessionDep,
    ) -> TrackRead:
        ensure_default_rating_factors(session)
        track = session.scalar(track_query().where(Track.id == track_id))
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        apply_track_update(session, track, payload)
        session.commit()
        track = session.scalar(track_query().where(Track.id == track_id))
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found after update")
        return track_to_schema(track)

    @app.post("/scan", response_model=ScanResponse)
    def scan(
        payload: ScanRequest,
        session: SessionDep,
    ) -> ScanResponse:
        ensure_default_rating_factors(session)
        result = scan_library(
            session,
            Path(payload.library),
            create_tag_groups=payload.create_tag_groups,
        )
        return ScanResponse(**result.__dict__)

    @app.post("/queue/generate", response_model=QueueRunRead)
    def generate_queue(
        payload: QueueGenerateRequest,
        session: SessionDep,
        settings: SettingsDep,
    ) -> QueueRunRead:
        ensure_default_rating_factors(session)
        effective_settings = get_effective_settings(session, settings)
        run, _items = generate_and_persist_playlist(
            session,
            effective_settings,
            length=payload.length,
            seed=payload.seed,
            write_debug_log=payload.explain,
        )
        return load_run_response(session, run.id)

    @app.get("/playlist-runs/{run_id}", response_model=QueueRunRead)
    def read_playlist_run(run_id: int, session: SessionDep) -> QueueRunRead:
        return load_run_response(session, run_id)

    @app.get("/playlist-runs/{run_id}/m3u8")
    def export_run_m3u8(run_id: int, session: SessionDep) -> PlainTextResponse:
        run = session.scalar(run_query().where(PlaylistRun.id == run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Playlist run not found")
        lines = ["#EXTM3U"]
        for item in run.items:
            if item.media_asset and item.media_asset.file_path:
                lines.append(item.media_asset.file_path)
        return PlainTextResponse("\n".join(lines) + "\n", media_type="audio/x-mpegurl")

    @app.get("/media/{asset_id}")
    def stream_media(asset_id: int, session: SessionDep) -> FileResponse:
        asset = session.get(MediaAsset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Media asset not found")
        path = Path(asset.file_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Media file missing from disk")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.post("/playback-events", response_model=PlaybackEventRead)
    def create_playback_event(
        payload: PlaybackEventCreate,
        session: SessionDep,
    ) -> PlaybackEventRead:
        if session.get(Track, payload.track_id) is None:
            raise HTTPException(status_code=404, detail="Track not found")
        event = PlaybackEvent(
            event_type=payload.event_type,
            track_id=payload.track_id,
            media_asset_id=payload.media_asset_id,
            playlist_run_id=payload.playlist_run_id,
            queue_position=payload.queue_position,
            progress_seconds=payload.progress_seconds,
            duration_seconds=payload.duration_seconds,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return playback_event_to_schema(event)

    @app.get("/playback-events", response_model=list[PlaybackEventRead])
    def list_playback_events(
        session: SessionDep,
        limit: int = 100,
    ) -> list[PlaybackEventRead]:
        bounded_limit = min(max(limit, 1), 500)
        events = session.scalars(
            select(PlaybackEvent)
            .order_by(PlaybackEvent.created_at.desc())
            .limit(bounded_limit)
        ).all()
        return [playback_event_to_schema(event) for event in events]

    return app


def track_query():
    return select(Track).options(
        selectinload(Track.assets),
        selectinload(Track.memberships).selectinload(GroupMembership.group),
        selectinload(Track.cooldown_tags).selectinload(TrackCooldownTag.tag),
        selectinload(Track.ratings).selectinload(TrackRating.factor),
    )


def run_query():
    return select(PlaylistRun).options(
        selectinload(PlaylistRun.items)
        .selectinload("*"),
    )


def load_run_response(session: Session, run_id: int) -> QueueRunRead:
    run = session.scalar(run_query().where(PlaylistRun.id == run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Playlist run not found")
    return QueueRunRead(
        id=run.id,
        seed=run.seed,
        length=run.length,
        items=[
            QueueItemRead(
                position=item.position,
                track=track_to_schema(item.track),
                media_asset_id=item.media_asset_id,
                media_url=f"/media/{item.media_asset_id}" if item.media_asset_id else None,
                score=item.score,
                explanation=json.loads(item.explanation_json or "{}"),
            )
            for item in run.items
        ],
    )


def track_to_schema(track: Track) -> TrackRead:
    return TrackRead(
        id=track.id,
        song_id=track.song_id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        has_lyrics=track.has_lyrics,
        sub_group=track.sub_group,
        manual_multiplier=track.manual_multiplier,
        assets=[
            {
                "id": asset.id,
                "file_path": asset.file_path,
                "asset_type": asset.asset_type,
                "codec": asset.codec,
                "container": asset.container,
                "source": asset.source,
                "source_quality": asset.source_quality,
                "is_lossless": asset.is_lossless,
                "checksum": asset.checksum,
                "browser_supported": asset.browser_supported,
            }
            for asset in track.assets
        ],
        groups=[
            {
                "id": membership.group.id,
                "name": membership.group.name,
                "group_type": membership.group.group_type,
                "share": membership.share,
            }
            for membership in track.memberships
            if membership.group is not None
        ],
        cooldown_tags=[link.tag.name for link in track.cooldown_tags if link.tag is not None],
        ratings={
            rating.factor.key: rating.value
            for rating in track.ratings
            if rating.factor is not None
        },
    )


def group_to_schema(group: WeightGroup) -> GroupRead:
    return GroupRead(
        id=group.id,
        name=group.name,
        group_type=group.group_type,
        manual_multiplier=group.manual_multiplier,
        rating_multiplier=group.rating_multiplier,
    )


def rating_factor_to_schema(factor: RatingFactor) -> RatingFactorRead:
    return RatingFactorRead(
        id=factor.id,
        key=factor.key,
        label=factor.label,
        weight=factor.weight,
        applies_to_lyrics=factor.applies_to_lyrics,
        applies_to_instrumental=factor.applies_to_instrumental,
        applies_to_variants_only=factor.applies_to_variants_only,
        enabled=factor.enabled,
    )


def playback_event_to_schema(event: PlaybackEvent) -> PlaybackEventRead:
    return PlaybackEventRead(
        id=event.id,
        event_type=event.event_type,
        track_id=event.track_id,
        media_asset_id=event.media_asset_id,
        playlist_run_id=event.playlist_run_id,
        queue_position=event.queue_position,
        progress_seconds=event.progress_seconds,
        duration_seconds=event.duration_seconds,
        created_at=event.created_at.isoformat(),
    )


def apply_track_update(session: Session, track: Track, payload: TrackUpdate) -> None:
    fields = payload.model_dump(exclude_unset=True)
    for field in ["title", "artist", "album", "has_lyrics", "sub_group", "manual_multiplier"]:
        if field in fields:
            setattr(track, field, fields[field])
    if payload.groups is not None:
        replace_groups(session, track, payload.groups)
    if payload.cooldown_tags is not None:
        replace_tags(session, track, payload.cooldown_tags)
    if payload.ratings is not None:
        upsert_ratings(session, track, payload.ratings)


def replace_groups(session: Session, track: Track, groups: list[TrackGroupWrite]) -> None:
    session.execute(delete(GroupMembership).where(GroupMembership.track_id == track.id))
    session.flush()
    for group_payload in groups:
        group = session.scalar(select(WeightGroup).where(WeightGroup.name == group_payload.name))
        if group is None:
            group = WeightGroup(name=group_payload.name, group_type=group_payload.group_type)
            session.add(group)
            session.flush()
        else:
            group.group_type = group_payload.group_type or group.group_type
        session.add(GroupMembership(track=track, group=group, share=group_payload.share))


def replace_tags(session: Session, track: Track, tag_names: list[str]) -> None:
    session.execute(delete(TrackCooldownTag).where(TrackCooldownTag.track_id == track.id))
    session.flush()
    for name in tag_names:
        cleaned = name.strip()
        if not cleaned:
            continue
        tag = session.scalar(select(CooldownTag).where(CooldownTag.name == cleaned))
        if tag is None:
            tag = CooldownTag(name=cleaned)
            session.add(tag)
            session.flush()
        session.add(TrackCooldownTag(track=track, tag=tag))


def upsert_ratings(session: Session, track: Track, ratings: dict[str, float | None]) -> None:
    factor_map = {factor.key: factor for factor in session.scalars(select(RatingFactor))}
    for key, value in ratings.items():
        factor = factor_map.get(key)
        if factor is None:
            continue
        rating = session.scalar(
            select(TrackRating).where(
                TrackRating.track_id == track.id,
                TrackRating.factor_id == factor.id,
            )
        )
        if rating is None:
            rating = TrackRating(track=track, factor=factor)
            session.add(rating)
        rating.value = None if value is None else min(max(float(value), 0.0), 5.0)
