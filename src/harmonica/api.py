from __future__ import annotations

import json
import mimetypes
from contextlib import asynccontextmanager
from datetime import UTC, timedelta
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from harmonica.bootstrap import ensure_default_rating_factors
from harmonica.config import Settings, get_settings, path_within_root
from harmonica.cover_ranking import next_pair, owner_set_state, record_verdict, set_summary
from harmonica.db import SessionLocal, get_session, init_db
from harmonica.embeds import is_valid_external_id, known_providers, parse_embed_url
from harmonica.history import playback_event_signal
from harmonica.http_security import install_security
from harmonica.models import (
    FAVOURITE_TAG_NAME,
    IGNORED_TAG_NAME,
    CooldownTag,
    CoverSetState,
    DeviceConfig,
    DeviceConfigTrack,
    Embed,
    GroupMembership,
    MediaAsset,
    PlaybackEvent,
    PlaylistItem,
    PlaylistRun,
    RatingFactor,
    RatingSample,
    Tag,
    Track,
    TrackCooldownTag,
    TrackRating,
    TrackTag,
    WeightGroup,
    favourite_track_ids,
    materialise_shared_assignments,
    now_utc,
    set_favourite_tag,
    tag_track_ids,
    visible_tag_rows,
    visible_tags_by_track,
)
from harmonica.normalization import plain_rating_averages
from harmonica.playlist import generate_and_persist_playlist, preferred_asset
from harmonica.scanner import scan_library
from harmonica.schemas import (
    CoverComparisonPair,
    CoverRenditionRead,
    CoverSetRead,
    CoverVerdictCreate,
    DeviceConfigClaim,
    DeviceConfigCreate,
    DeviceConfigDetail,
    DeviceConfigSummary,
    DeviceConfigUpdate,
    EmbedWrite,
    GroupRead,
    LibraryImportRequest,
    PlaybackEventCreate,
    PlaybackEventRead,
    PlaylistRunRename,
    PlaylistRunSummary,
    QueueGenerateRequest,
    QueueItemRead,
    QueueRunRead,
    RatingFactorRead,
    ScanRequest,
    ScanResponse,
    SettingsRead,
    SettingsUpdate,
    SpotifyPlaylistRead,
    SpotifyTrackRead,
    StatsSummaryRead,
    TagCreate,
    TagRead,
    TagUpdate,
    TrackGroupWrite,
    TrackRead,
    TrackUpdate,
    YouTubeClusterRead,
    YouTubeImportPreview,
    YouTubeImportRequest,
    YouTubeVideoRead,
)
from harmonica.security import (
    hash_passphrase,
    issue_config_token,
    verify_config_token,
    verify_passphrase,
)
from harmonica.serialization import (
    EXPORT_SCOPES,
    export_library_payload,
    import_library_payload,
)
from harmonica.settings_store import get_effective_settings, settings_payload, update_setting_values
from harmonica.spotify import SpotifyError, fetch_playlist
from harmonica.youtube_import import (
    MAX_VIDEOS,
    MAX_VIDEOS_KEYLESS,
    YouTubeImportError,
    extract_video_ids,
    fetch_via_data_api,
    fetch_via_oembed,
    normalise_factors,
    requires_api_key,
)
from harmonica.youtube_organize import organize

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_owner(
    request: Request, session: SessionDep, settings: SettingsDep
) -> DeviceConfig | None:
    """Resolve the requesting user profile, or None for legacy/local (whole-library) mode.

    Identity comes from a signed ``Authorization: Bearer <token>`` (tamper-proof — issued only after
    a verified passphrase). The raw ``X-Harmonica-Config-Id`` header is a spoofable convenience that
    gives structural separation but NOT access control, so it is honoured ONLY in local (loopback)
    mode. In exposed mode it is ignored: identity must come from a signed token, or the request is
    treated as unauthenticated (and the security middleware will already have refused any private
    or state-changing route)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        config_id = verify_config_token(auth[7:].strip(), settings.effective_secret_key())
        if config_id is None:
            raise HTTPException(status_code=401, detail="Invalid profile token")
    elif getattr(request.app.state, "auth_required", False):
        # No token in exposed mode: never resolve a profile from a client-supplied id.
        return None
    else:
        raw = request.headers.get("x-harmonica-config-id")
        if not raw:
            return None
        try:
            config_id = int(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid profile id") from exc
    config = session.get(DeviceConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return config


OwnerDep = Annotated[DeviceConfig | None, Depends(get_owner)]


def owner_library_ids(owner: DeviceConfig | None) -> set[int] | None:
    """The set of track ids in a profile's private library, or None for legacy/local (whole
    library). An empty set means a brand-new profile that hasn't imported anything yet."""
    if owner is None:
        return None
    return {link.track_id for link in owner.tracks}


def owner_favourite_lookup(session: Session, owner: DeviceConfig | None) -> set[int] | None:
    """A profile's favourite track ids, or None in legacy/local mode (favourite reads off the
    shared Track column). A favourite is one user's private opinion of a shared song."""
    if owner is None:
        return None
    return favourite_track_ids(session, owner.id)


def resolve_favourite(track: Track, favourites: set[int] | None) -> bool:
    """Favourite for this request: the profile's own tag when owned, else the shared Track flag."""
    if favourites is None:
        return bool(track.favourite)
    return track.id in favourites


def set_owner_favourite(
    session: Session, config_id: int, track_id: int, value: bool
) -> None:
    """Write a profile's private favourite tag onto its per-user link to a shared track."""
    link = session.scalar(
        select(DeviceConfigTrack).where(
            DeviceConfigTrack.config_id == config_id,
            DeviceConfigTrack.track_id == track_id,
        )
    )
    if link is None:
        link = DeviceConfigTrack(config_id=config_id, track_id=track_id)
        session.add(link)
    link.favourite = value


def create_app() -> FastAPI:
    # init_db() now also runs the additive-column upgrades + rating-sample backfill.
    init_db()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        with SessionLocal() as session:
            ensure_default_rating_factors(session)
        yield

    app = FastAPI(title="Harmonica", version="0.1.0", lifespan=lifespan)

    # Security policy read by the middleware (see http_security.py). In exposed mode (bound off
    # loopback, or require_auth forced on) every non-public endpoint needs a valid profile token;
    # in local mode this is a no-op. CSRF and security headers apply in both modes.
    settings = get_settings()
    app.state.auth_required = settings.auth_required()
    app.state.secret = settings.effective_secret_key()
    app.state.allowed_origins = {"http://localhost:5173", "http://127.0.0.1:5173"}
    install_security(app)

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

    @app.get("/youtube/config")
    def youtube_config(session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
        # Tells the frontend whether to load YouTube's official player, and whether Data API
        # metadata lookups are available. It exposes only the PRESENCE of the key (a boolean),
        # never the key itself — the key stays server-side.
        effective = get_effective_settings(session, settings)
        return {
            "enabled": effective.youtube_embed_enabled,
            "has_api_key": settings.effective_youtube_data_api_key() is not None,
            "providers": list(known_providers()),
        }

    @app.get("/spotify/config")
    def spotify_config(session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
        # Reports only whether the feature is on and whether app credentials are present (a
        # boolean). It never exposes the client id or secret. The browser never talks to Spotify;
        # only this daemon does, so the credentials stay server-side.
        effective = get_effective_settings(session, settings)
        return {
            "enabled": effective.spotify_enabled,
            "has_credentials": settings.spotify_credentials() is not None,
        }

    @app.get("/spotify/playlist")
    def spotify_playlist(
        session: SessionDep,
        settings: SettingsDep,
        url: Annotated[str, Query(max_length=400)],
    ) -> SpotifyPlaylistRead:
        # Reads a public playlist's track metadata server-side. Gated on the feature being enabled
        # AND credentials being present, so a request never reaches Spotify otherwise. The only
        # user input is the playlist reference, which spotify.py validates to a strict id.
        effective = get_effective_settings(session, settings)
        if not effective.spotify_enabled:
            raise HTTPException(status_code=403, detail="Spotify reading is turned off")
        credentials = settings.spotify_credentials()
        if credentials is None:
            raise HTTPException(status_code=400, detail="Spotify app credentials are not set")
        client_id, client_secret = credentials
        try:
            playlist = fetch_playlist(client_id, client_secret, url)
        except SpotifyError as exc:
            # The message is safe (never contains the secret or token); surface it to the user.
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return SpotifyPlaylistRead(
            id=playlist.id,
            name=playlist.name,
            truncated=playlist.truncated,
            tracks=[
                SpotifyTrackRead(
                    name=track.name,
                    artists=track.artists,
                    album=track.album,
                    duration_ms=track.duration_ms,
                    spotify_id=track.spotify_id,
                    url=track.url,
                )
                for track in playlist.tracks
            ],
        )

    @app.post("/youtube/import-preview")
    def youtube_import_preview(
        payload: YouTubeImportRequest,
        session: SessionDep,
        settings: SettingsDep,
    ) -> YouTubeImportPreview:
        # Reads the metadata of a pasted list of YouTube videos server-side and organises them into
        # proposed tracks, WITHOUT writing anything: the result flows into the review screen. Gated
        # on YouTube playback being enabled, so no request reaches YouTube otherwise. Factors that
        # need the Data API are refused (with guidance) unless the user's key is present.
        effective = get_effective_settings(session, settings)
        if not effective.youtube_embed_enabled:
            raise HTTPException(status_code=403, detail="YouTube playback is turned off")
        factors = normalise_factors(payload.factors)
        api_key = settings.effective_youtube_data_api_key()
        if requires_api_key(factors) and not api_key:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Some chosen factors (like duration or description) need a YouTube Data API "
                    "key, which is not set. Add one on the server, or unpick those factors."
                ),
            )
        video_ids = extract_video_ids(payload.links)
        if not video_ids:
            raise HTTPException(
                status_code=400, detail="No YouTube video links were found in that text."
            )
        requested = len(video_ids)
        cap = MAX_VIDEOS if (requires_api_key(factors) and api_key) else MAX_VIDEOS_KEYLESS
        truncated = requested > cap
        video_ids = video_ids[:cap]
        try:
            if requires_api_key(factors) and api_key:
                metas = fetch_via_data_api(video_ids, api_key)
                used_api = True
            else:
                metas = fetch_via_oembed(video_ids)
                used_api = False
        except YouTubeImportError as exc:
            # The message is safe (it never contains the key); surface it to the user.
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        result = organize(metas, factors)
        return YouTubeImportPreview(
            videos=[
                YouTubeVideoRead(
                    video_id=summary.video_id,
                    title=summary.title,
                    channel=summary.channel,
                    duration_seconds=summary.duration_seconds,
                    available=summary.available,
                    likely_song=summary.likely_song,
                )
                for summary in result.videos
            ],
            tracks=result.tracks,
            clusters=[
                YouTubeClusterRead(
                    key=cluster.key,
                    suggested_sub_group=cluster.suggested_sub_group,
                    song_ids=cluster.song_ids,
                    reason=cluster.reason,
                )
                for cluster in result.clusters
            ],
            used_api=used_api,
            truncated=truncated,
            requested=requested,
        )

    def cover_set_read(
        session: Session,
        sub_group: str,
        settings: Settings,
        owner: DeviceConfig | None = None,
    ) -> CoverSetRead:
        owner_id = owner.id if owner else None
        phase, total, rows = set_summary(session, sub_group, settings, owner_config_id=owner_id)
        return CoverSetRead(
            sub_group=sub_group,
            comparison_phase=phase,
            total_comparisons=total,
            renditions=[
                CoverRenditionRead(
                    track_id=track_id,
                    sub_group=sub_group,
                    bt_strength=strength,
                    comparison_count=count,
                )
                for track_id, strength, count in rows
            ],
        )

    @app.get("/cover-sets/{sub_group}", response_model=CoverSetRead)
    def read_cover_set(
        sub_group: str, session: SessionDep, settings: SettingsDep, owner: OwnerDep
    ) -> CoverSetRead:
        return cover_set_read(session, sub_group, settings, owner)

    @app.post("/cover-sets/{sub_group}/reopen", response_model=CoverSetRead)
    def reopen_cover_set(
        sub_group: str, session: SessionDep, settings: SettingsDep, owner: OwnerDep
    ) -> CoverSetRead:
        # "Compare again": a settled set goes back to prompting. Verdicts are kept; the ranking just
        # reopens to fresh evidence (e.g. a rendition was re-encoded, or tastes changed).
        if owner is not None:
            owner_state = owner_set_state(session, sub_group, owner.id)
            if owner_state is not None and owner_state.comparison_phase == "settled":
                owner_state.comparison_phase = "bootstrapping"
                session.commit()
        else:
            state = session.get(CoverSetState, sub_group)
            if state is not None and state.comparison_phase == "settled":
                state.comparison_phase = "bootstrapping"
                session.commit()
        return cover_set_read(session, sub_group, settings, owner)

    def comparison_item(
        track: Track, role: str, peer_id: int, sub_group: str
    ) -> QueueItemRead | None:
        asset = preferred_asset(track)
        if asset is None:
            return None  # no playable media — can't stage a head-to-head
        return QueueItemRead(
            position=-1,  # synthetic: spliced into the queue client-side, not a stored run item
            track=track_to_schema(track),
            media_asset_id=asset.id,
            media_url=f"/media/{asset.id}",
            score=0.0,
            explanation={
                "comparison": {"set_id": sub_group, "role": role, "peer_track_id": peer_id}
            },
        )

    @app.get("/cover-comparisons/next", response_model=CoverComparisonPair | None)
    def next_cover_comparison(
        sub_group: str,
        session: SessionDep,
        settings: SettingsDep,
        owner: OwnerDep,
    ) -> CoverComparisonPair | None:
        if not settings.cover_comparison_enabled:
            return None
        pair = next_pair(session, sub_group, settings, owner_config_id=owner.id if owner else None)
        if pair is None:
            return None
        track_a = session.scalar(track_query().where(Track.id == pair[0]))
        track_b = session.scalar(track_query().where(Track.id == pair[1]))
        if track_a is None or track_b is None:
            return None
        item_a = comparison_item(track_a, "a", pair[1], sub_group)
        item_b = comparison_item(track_b, "b", pair[0], sub_group)
        if item_a is None or item_b is None:
            return None
        return CoverComparisonPair(sub_group=sub_group, a=item_a, b=item_b)

    @app.post("/cover-verdicts", response_model=CoverSetRead)
    def submit_cover_verdict(
        payload: CoverVerdictCreate,
        session: SessionDep,
        settings: SettingsDep,
        owner: OwnerDep,
    ) -> CoverSetRead:
        # Both tracks must really belong to the named cover set, and a winner (if given) must be one
        # of them — otherwise the Bradley-Terry fit would be silently fed a bogus comparison.
        members = set(
            session.scalars(select(Track.id).where(Track.sub_group == payload.sub_group)).all()
        )
        if payload.track_a_id not in members or payload.track_b_id not in members:
            raise HTTPException(status_code=400, detail="Both renditions must be in the cover set.")
        if payload.track_a_id == payload.track_b_id:
            raise HTTPException(status_code=400, detail="A rendition cannot be compared to itself.")
        if payload.winner_track_id is not None and payload.winner_track_id not in (
            payload.track_a_id,
            payload.track_b_id,
        ):
            raise HTTPException(status_code=400, detail="Winner must be one of the two renditions.")
        record_verdict(
            session,
            sub_group=payload.sub_group,
            track_a_id=payload.track_a_id,
            track_b_id=payload.track_b_id,
            winner_track_id=payload.winner_track_id,
            settings=settings,
            pct_a=payload.pct_a,
            pct_b=payload.pct_b,
            session_id=payload.session_id,
            run_id=payload.run_id,
            owner_config_id=owner.id if owner else None,
        )
        session.commit()
        return cover_set_read(session, payload.sub_group, settings, owner)

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
    def list_tracks(session: SessionDep, owner: OwnerDep) -> list[TrackRead]:
        library_ids = owner_library_ids(owner)
        if library_ids is not None and not library_ids:
            return []  # brand-new profile: empty library
        query = track_query().order_by(Track.artist, Track.album, Track.title)
        if library_ids is not None:
            query = query.where(Track.id.in_(library_ids))
        tracks = session.scalars(query).all()
        averages = plain_rating_averages(session, owner_config_id=owner.id if owner else None)
        favourites = owner_favourite_lookup(session, owner)
        tags_map = visible_tags_by_track(session, owner.id if owner else None)
        return [
            track_to_schema(
                track,
                averages.get(track.id) or {},
                favourite=resolve_favourite(track, favourites),
                tags=tags_map.get(track.id),
            )
            for track in tracks
        ]

    @app.get("/tracks/{track_id}", response_model=TrackRead)
    def read_track(track_id: int, session: SessionDep, owner: OwnerDep) -> TrackRead:
        library_ids = owner_library_ids(owner)
        if library_ids is not None and track_id not in library_ids:
            raise HTTPException(status_code=404, detail="Track not found")
        track = session.scalar(track_query().where(Track.id == track_id))
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        averages = plain_rating_averages(
            session, [track_id], owner_config_id=owner.id if owner else None
        )
        favourite = resolve_favourite(track, owner_favourite_lookup(session, owner))
        tags = visible_tags_by_track(session, owner.id if owner else None).get(track_id)
        return track_to_schema(track, averages.get(track_id) or {}, favourite=favourite, tags=tags)

    @app.patch("/tracks/{track_id}", response_model=TrackRead)
    def update_track(
        track_id: int,
        payload: TrackUpdate,
        session: SessionDep,
        owner: OwnerDep,
    ) -> TrackRead:
        ensure_default_rating_factors(session)
        library_ids = owner_library_ids(owner)
        if library_ids is not None and track_id not in library_ids:
            raise HTTPException(status_code=404, detail="Track not found")
        track = session.scalar(track_query().where(Track.id == track_id))
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        apply_track_update(session, track, payload, owner_config_id=owner.id if owner else None)
        session.commit()
        track = session.scalar(track_query().where(Track.id == track_id))
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found after update")
        averages = plain_rating_averages(
            session, [track_id], owner_config_id=owner.id if owner else None
        )
        favourite = resolve_favourite(track, owner_favourite_lookup(session, owner))
        tags = visible_tags_by_track(session, owner.id if owner else None).get(track_id)
        return track_to_schema(track, averages.get(track_id) or {}, favourite=favourite, tags=tags)

    @app.post("/scan", response_model=ScanResponse)
    def scan(
        payload: ScanRequest,
        session: SessionDep,
        settings: SettingsDep,
        owner: OwnerDep,
    ) -> ScanResponse:
        # Only scan inside the media root, so /scan can't be aimed at "/" to index
        # (and then serve) arbitrary files or exhaust the host walking the disk.
        root = path_within_root(payload.library, settings.effective_media_root)
        if root is None:
            raise HTTPException(
                status_code=400,
                detail="Scan path must be inside the configured media root.",
            )
        ensure_default_rating_factors(session)
        result = scan_library(
            session,
            root,
            create_tag_groups=payload.create_tag_groups,
            owner_config_id=owner.id if owner else None,
        )
        return ScanResponse(**result.__dict__)

    @app.post("/queue/generate", response_model=QueueRunRead)
    def generate_queue(
        payload: QueueGenerateRequest,
        session: SessionDep,
        settings: SettingsDep,
        owner: OwnerDep,
    ) -> QueueRunRead:
        ensure_default_rating_factors(session)
        effective_settings = get_effective_settings(session, settings)
        included_track_ids: set[int] | None = None
        owner_config_id: int | None = None
        # An authenticated profile (header) is the authority: its library is the candidate pool
        # (empty allowed = empty library) and its listening profile owns the run. The legacy
        # body `config_id` path is kept only for no-owner (local) callers.
        config = owner
        if config is None and payload.config_id is not None:
            config = session.get(DeviceConfig, payload.config_id)
            if config is None:
                raise HTTPException(status_code=404, detail="Config not found")
        if config is not None:
            effective_settings = apply_config_settings(effective_settings, config)
            ids = [link.track_id for link in config.tracks]
            if owner is not None:
                included_track_ids = set(ids)  # owned: empty stays empty
                owner_config_id = owner.id
            else:
                included_track_ids = set(ids) if ids else None  # legacy: empty selection = all
        requested_tags = [
            name.strip()
            for name in (payload.tags or [])
            if name.strip() and name.strip() != IGNORED_TAG_NAME
        ]
        if requested_tags:
            # Union: a track carrying ANY requested tag qualifies; intersected with the
            # profile's library. Unknown names contribute nothing (an empty pool = empty run).
            tag_pool = tag_track_ids(session, requested_tags, owner.id if owner else None)
            included_track_ids = (
                tag_pool if included_track_ids is None else included_track_ids & tag_pool
            )
        run, _items = generate_and_persist_playlist(
            session,
            effective_settings,
            length=payload.length,
            seed=payload.seed,
            write_debug_log=payload.explain,
            ui_active=payload.ui_active,
            included_track_ids=included_track_ids,
            owner_config_id=owner_config_id,
            queue_tags=requested_tags or None,
        )
        return load_run_response(session, run.id)

    @app.get("/playlist-runs", response_model=list[PlaylistRunSummary])
    def list_playlist_runs(
        session: SessionDep, owner: OwnerDep, limit: int = 50
    ) -> list[PlaylistRunSummary]:
        bounded_limit = min(max(limit, 1), 200)
        runs = session.scalars(
            scope_runs(run_summary_query(), owner)
            .order_by(PlaylistRun.created_at.desc(), PlaylistRun.id.desc())
            .limit(bounded_limit)
        ).all()
        return [playlist_run_to_summary(run) for run in runs]

    @app.get("/playlist-runs/{run_id}", response_model=QueueRunRead)
    def read_playlist_run(run_id: int, session: SessionDep, owner: OwnerDep) -> QueueRunRead:
        require_owned_run(session, run_id, owner)
        return load_run_response(session, run_id)

    @app.patch("/playlist-runs/{run_id}", response_model=PlaylistRunSummary)
    def rename_playlist_run(
        run_id: int,
        payload: PlaylistRunRename,
        session: SessionDep,
        owner: OwnerDep,
    ) -> PlaylistRunSummary:
        run = session.scalar(scope_runs(run_summary_query(), owner).where(PlaylistRun.id == run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Playlist run not found")
        run.name = clean_playlist_run_name(payload.name)
        session.commit()
        run = session.scalar(run_summary_query().where(PlaylistRun.id == run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Playlist run not found after rename")
        return playlist_run_to_summary(run)

    @app.delete("/playlist-runs/{run_id}", status_code=204)
    def delete_playlist_run(run_id: int, session: SessionDep, owner: OwnerDep) -> Response:
        run = require_owned_run(session, run_id, owner)
        session.delete(run)
        session.commit()
        return Response(status_code=204)

    @app.get("/playlist-runs/{run_id}/m3u8")
    def export_run_m3u8(
        run_id: int, session: SessionDep, owner: OwnerDep
    ) -> PlainTextResponse:
        require_owned_run(session, run_id, owner)
        run = session.scalar(run_query().where(PlaylistRun.id == run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Playlist run not found")
        lines = ["#EXTM3U"]
        for item in run.items:
            if item.media_asset and item.media_asset.file_path:
                lines.append(item.media_asset.file_path)
        return PlainTextResponse("\n".join(lines) + "\n", media_type="audio/x-mpegurl")

    @app.get("/media/{asset_id}")
    def stream_media(
        asset_id: int, session: SessionDep, settings: SettingsDep
    ) -> FileResponse:
        asset = session.get(MediaAsset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Media asset not found")
        # Confine serving to the media root: a crafted file_path (e.g. from an
        # imported library) pointing outside it is treated as missing, not served.
        path = path_within_root(asset.file_path, settings.effective_media_root)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="Media file missing from disk")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.post("/playback-events", response_model=PlaybackEventRead)
    def create_playback_event(
        payload: PlaybackEventCreate,
        session: SessionDep,
        owner: OwnerDep,
    ) -> PlaybackEventRead:
        if session.get(Track, payload.track_id) is None:
            raise HTTPException(status_code=404, detail="Track not found")
        event = PlaybackEvent(
            event_type=payload.event_type,
            track_id=payload.track_id,
            owner_config_id=owner.id if owner else None,
            media_asset_id=payload.media_asset_id,
            playlist_run_id=payload.playlist_run_id,
            queue_position=payload.queue_position,
            progress_seconds=payload.progress_seconds,
            duration_seconds=payload.duration_seconds,
            avg_level=payload.avg_level,
            peak_level=payload.peak_level,
            output_gain=payload.output_gain,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return playback_event_to_schema(event)

    @app.get("/playback-events", response_model=list[PlaybackEventRead])
    def list_playback_events(
        session: SessionDep,
        owner: OwnerDep,
        limit: int = 100,
    ) -> list[PlaybackEventRead]:
        bounded_limit = min(max(limit, 1), 500)
        query = select(PlaybackEvent)
        if owner is not None:
            query = query.where(PlaybackEvent.owner_config_id == owner.id)
        else:
            query = query.where(PlaybackEvent.owner_config_id.is_(None))
        events = session.scalars(
            query.order_by(PlaybackEvent.created_at.desc()).limit(bounded_limit)
        ).all()
        return [playback_event_to_schema(event) for event in events]

    @app.get("/stats/summary", response_model=StatsSummaryRead)
    def stats_summary(session: SessionDep, owner: OwnerDep) -> StatsSummaryRead:
        library_ids = owner_library_ids(owner)
        track_q = track_query()
        event_q = select(PlaybackEvent)
        if owner is not None:
            # Scope to the profile's library (a sentinel -1 keeps an empty library returning none).
            track_q = track_q.where(Track.id.in_(library_ids or {-1}))
            event_q = event_q.where(PlaybackEvent.owner_config_id == owner.id)
        else:
            event_q = event_q.where(PlaybackEvent.owner_config_id.is_(None))
        tracks = list(session.scalars(track_q))
        events = list(session.scalars(event_q))
        # A track counts as rated when this profile has a non-null rating for it (owned: from the
        # profile's own samples; legacy: the shared latest-star cache).
        if owner is not None:
            averages = plain_rating_averages(
                session, list(library_ids) if library_ids else [], owner_config_id=owner.id
            )
            rated_track_ids = set(averages.keys())
        else:
            rated_track_ids = {
                track.id
                for track in tracks
                if any(rating.value is not None for rating in track.ratings)
            }
        video_track_ids = {
            track.id
            for track in tracks
            if any(asset.asset_type == "video" for asset in track.assets)
        }
        early_skip_count = 0
        partial_skip_count = 0
        skipped_count = 0
        completed_count = 0
        for event in events:
            if event.event_type == "completed":
                completed_count += 1
            if event.event_type == "skipped":
                skipped_count += 1
                repeat_credit, skip_penalty = playback_event_signal(event)
                if repeat_credit == 0 and skip_penalty > 0:
                    early_skip_count += 1
                elif repeat_credit < 1 and skip_penalty > 0:
                    partial_skip_count += 1
        group_count = len(session.scalars(select(WeightGroup.id)).all())
        return StatsSummaryRead(
            track_count=len(tracks),
            rated_track_count=len(rated_track_ids),
            unrated_track_count=max(len(tracks) - len(rated_track_ids), 0),
            video_track_count=len(video_track_ids),
            group_count=group_count,
            playback_event_count=len(events),
            completed_count=completed_count,
            skipped_count=skipped_count,
            early_skip_count=early_skip_count,
            partial_skip_count=partial_skip_count,
        )

    @app.get("/library/export-json")
    def export_library_json(
        session: SessionDep, owner: OwnerDep, scope: str = "all"
    ) -> dict[str, Any]:
        """One payload, four scopes: ``metadata`` (songs and groups), ``ratings`` (stars and
        their history), ``settings`` (the adjustable controls), or ``all``. The client saves
        it as a file; POST /library/import-json takes any of them back."""
        if scope not in EXPORT_SCOPES:
            raise HTTPException(
                status_code=422,
                detail="scope must be one of: " + ", ".join(EXPORT_SCOPES),
            )
        return export_library_payload(
            session, owner_config_id=owner.id if owner else None, scope=scope
        )

    @app.post("/library/import-json")
    def import_library_json(
        payload: LibraryImportRequest,
        session: SessionDep,
        settings: SettingsDep,
        owner: OwnerDep,
    ) -> dict[str, Any]:
        summary = import_library_payload(
            session, payload.payload, settings=settings, owner_config_id=owner.id if owner else None
        )
        return {"ok": True, **summary}

    # --- Tags (organisational labels; system tags Favourite/Ignored are fixed) ---

    @app.get("/tags", response_model=list[TagRead])
    def list_tags(session: SessionDep, owner: OwnerDep) -> list[TagRead]:
        counts: dict[int, set[int]] = {}
        for track_id, tag in visible_tag_rows(session, owner.id if owner else None):
            counts.setdefault(tag.id, set()).add(track_id)
        tags = session.scalars(select(Tag).order_by(Tag.kind.desc(), Tag.name)).all()
        return [tag_to_schema(tag, len(counts.get(tag.id, ()))) for tag in tags]

    @app.post("/tags", response_model=TagRead)
    def create_tag(payload: TagCreate, session: SessionDep) -> TagRead:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Tag name cannot be empty")
        if session.scalar(select(Tag).where(Tag.name == name)):
            raise HTTPException(status_code=409, detail="A tag with that name already exists")
        tag = Tag(
            name=name,
            kind="custom",
            shared=payload.shared,
            affects_algorithm=payload.affects_algorithm,
        )
        session.add(tag)
        session.commit()
        return tag_to_schema(tag, 0)

    @app.patch("/tags/{tag_id}", response_model=TagRead)
    def update_tag(
        tag_id: int, payload: TagUpdate, session: SessionDep, owner: OwnerDep
    ) -> TagRead:
        tag = session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        if tag.kind == "system":
            raise HTTPException(status_code=403, detail="System tags cannot be edited")
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="Tag name cannot be empty")
            clash = session.scalar(select(Tag).where(Tag.name == name, Tag.id != tag.id))
            if clash is not None:
                raise HTTPException(
                    status_code=409, detail="A tag with that name already exists"
                )
            tag.name = name
        if payload.shared is not None:
            if tag.shared and not payload.shared:
                # Unsharing must not take the tag away from anyone: every scope keeps its
                # own copy of what the household had.
                materialise_shared_assignments(session, tag.id)
            tag.shared = payload.shared
        if payload.affects_algorithm is not None:
            tag.affects_algorithm = payload.affects_algorithm
        session.commit()
        count = len(
            {
                track_id
                for track_id, visible in visible_tag_rows(
                    session, owner.id if owner else None
                )
                if visible.id == tag.id
            }
        )
        return tag_to_schema(tag, count)

    @app.delete("/tags/{tag_id}", status_code=204)
    def delete_tag(tag_id: int, session: SessionDep, owner: OwnerDep) -> Response:
        tag = session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        if tag.kind == "system":
            raise HTTPException(status_code=403, detail="System tags cannot be deleted")
        if owner is not None:
            # A profile deletes only its own assignments, shared tag or not. The definition
            # survives while any other scope still uses the tag, and goes once nobody does.
            session.execute(
                delete(TrackTag).where(
                    TrackTag.tag_id == tag.id, TrackTag.owner_config_id == owner.id
                )
            )
            session.flush()
            still_used = session.scalar(
                select(TrackTag.id).where(TrackTag.tag_id == tag.id).limit(1)
            )
            if still_used is None:
                session.delete(tag)
            session.commit()
            return Response(status_code=204)
        # Local mode is single-user administration: the tag and every assignment go together.
        # Explicit: SQLite FK cascades are not enforced through this connection.
        session.execute(delete(TrackTag).where(TrackTag.tag_id == tag.id))
        session.delete(tag)
        session.commit()
        return Response(status_code=204)

    # --- Device configs (multi-device profiles; see docs/planning/multi-device-architecture.md) ---

    @app.get("/configs", response_model=list[DeviceConfigSummary])
    def list_configs(session: SessionDep) -> list[DeviceConfigSummary]:
        configs = session.scalars(select(DeviceConfig).order_by(DeviceConfig.name)).all()
        return [
            DeviceConfigSummary(
                id=config.id,
                name=config.name,
                track_count=len(config.tracks),
                created_at=config.created_at.isoformat(),
            )
            for config in configs
        ]

    @app.post("/configs", response_model=DeviceConfigDetail)
    def create_config(
        payload: DeviceConfigCreate, session: SessionDep, settings: SettingsDep
    ) -> DeviceConfigDetail:
        if session.scalar(select(DeviceConfig).where(DeviceConfig.name == payload.name)):
            raise HTTPException(status_code=409, detail="A config with that name already exists")
        config = DeviceConfig(
            name=payload.name,
            passphrase_hash=hash_passphrase(payload.passphrase),
            settings_json=json.dumps(payload.settings or {}),
        )
        session.add(config)
        session.flush()
        set_config_tracks(session, config, payload.track_ids)
        session.commit()
        token = issue_config_token(config.id, settings.effective_secret_key())
        return config_to_detail(session, config.id, token=token)

    @app.post("/configs/claim", response_model=DeviceConfigDetail)
    def claim_config(
        payload: DeviceConfigClaim, session: SessionDep, settings: SettingsDep
    ) -> DeviceConfigDetail:
        config = session.scalar(select(DeviceConfig).where(DeviceConfig.name == payload.name))
        if config is None or not verify_passphrase(payload.passphrase, config.passphrase_hash):
            raise HTTPException(status_code=401, detail="Unknown config name or wrong passphrase")
        token = issue_config_token(config.id, settings.effective_secret_key())
        return config_to_detail(session, config.id, token=token)

    @app.patch("/configs/{config_id}", response_model=DeviceConfigDetail)
    def update_config(
        config_id: int,
        payload: DeviceConfigUpdate,
        session: SessionDep,
        settings: SettingsDep,
    ) -> DeviceConfigDetail:
        config = session.get(DeviceConfig, config_id)
        if config is None or not verify_passphrase(payload.passphrase, config.passphrase_hash):
            raise HTTPException(status_code=401, detail="Config not found or wrong passphrase")
        if payload.settings is not None:
            config.settings_json = json.dumps(payload.settings)
        if payload.track_ids is not None:
            set_config_tracks(session, config, payload.track_ids)
        session.commit()
        token = issue_config_token(config.id, settings.effective_secret_key())
        return config_to_detail(session, config_id, token=token)

    # Serve the built web UI from the daemon itself, so the local hosted-browser experience is just
    # "run the daemon, open the bound URL" — the same single artifact that, bound to 0.0.0.0, is the
    # NAS version. Mounted LAST so every API route above takes precedence; the SPA only catches the
    # remaining paths (index, assets, manifest, icons). API-only if no build is present.
    dist = get_settings().effective_web_dist
    if dist is not None:
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")

    return app


def set_config_tracks(session: Session, config: DeviceConfig, track_ids: list[int]) -> None:
    session.execute(delete(DeviceConfigTrack).where(DeviceConfigTrack.config_id == config.id))
    session.flush()
    seen: set[int] = set()
    for track_id in track_ids:
        if track_id in seen or session.get(Track, track_id) is None:
            continue
        seen.add(track_id)
        session.add(DeviceConfigTrack(config_id=config.id, track_id=track_id))


def config_to_detail(
    session: Session, config_id: int, token: str | None = None
) -> DeviceConfigDetail:
    config = session.get(DeviceConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return DeviceConfigDetail(
        id=config.id,
        name=config.name,
        settings=json.loads(config.settings_json or "{}"),
        included_track_ids=[link.track_id for link in config.tracks],
        token=token,
    )


def apply_config_settings(settings: Settings, config: DeviceConfig) -> Settings:
    raw = json.loads(config.settings_json or "{}")
    fields = type(settings).model_fields
    updates = {key: value for key, value in raw.items() if key in fields}
    return settings.model_copy(update=updates) if updates else settings


def track_query():
    return select(Track).options(
        selectinload(Track.assets),
        selectinload(Track.embeds),
        selectinload(Track.memberships).selectinload(GroupMembership.group),
        selectinload(Track.cooldown_tags).selectinload(TrackCooldownTag.tag),
        selectinload(Track.ratings).selectinload(TrackRating.factor),
    )


def run_query():
    return select(PlaylistRun).options(
        selectinload(PlaylistRun.items)
        .selectinload("*"),
    )


def run_summary_query():
    return select(PlaylistRun).options(
        selectinload(PlaylistRun.items).selectinload(PlaylistItem.track),
    )


def scope_runs(query, owner: DeviceConfig | None):
    """Restrict a PlaylistRun query to the requesting profile's own runs (legacy/local sees only
    unowned runs)."""
    if owner is None:
        return query.where(PlaylistRun.owner_config_id.is_(None))
    return query.where(PlaylistRun.owner_config_id == owner.id)


def require_owned_run(
    session: Session, run_id: int, owner: DeviceConfig | None
) -> PlaylistRun:
    run = session.get(PlaylistRun, run_id)
    expected = owner.id if owner else None
    if run is None or run.owner_config_id != expected:
        raise HTTPException(status_code=404, detail="Playlist run not found")
    return run


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


def playlist_run_to_summary(run: PlaylistRun) -> PlaylistRunSummary:
    sorted_items = sorted(run.items, key=lambda item: item.position)
    return PlaylistRunSummary(
        id=run.id,
        name=run.name,
        seed=run.seed,
        length=run.length,
        item_count=len(sorted_items),
        created_at=run.created_at.isoformat(),
        preview_titles=[
            item.track.title
            for item in sorted_items[:4]
            if item.track is not None
        ],
    )


def clean_playlist_run_name(name: str | None) -> str | None:
    if name is None:
        return None
    cleaned = name.strip()
    return cleaned or None


def track_to_schema(
    track: Track,
    ratings_average: dict[str, float] | None = None,
    favourite: bool = False,
    tags: list[str] | None = None,
) -> TrackRead:
    return TrackRead(
        id=track.id,
        song_id=track.song_id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        has_lyrics=track.has_lyrics,
        favourite=favourite,
        sub_group=track.sub_group,
        manual_multiplier=track.manual_multiplier,
        clip_start_seconds=track.clip_start_seconds,
        clip_end_seconds=track.clip_end_seconds,
        audio_only=track.audio_only,
        is_original_rendition=track.is_original_rendition,
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
        embeds=[
            {
                "id": embed.id,
                "provider": embed.provider,
                "external_id": embed.external_id,
                "url": embed.url,
                "start_seconds": embed.start_seconds,
            }
            for embed in track.embeds
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
        tags=tags or [],
        # The displayed rating is the plain AVERAGE of the user's past ratings (computed from
        # history); fall back to the raw latest star only when history hasn't been computed.
        ratings=(
            ratings_average
            if ratings_average is not None
            else {
                rating.factor.key: rating.value
                for rating in track.ratings
                if rating.factor is not None
            }
        ),
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


def tag_to_schema(tag: Tag, track_count: int) -> TagRead:
    return TagRead(
        id=tag.id,
        name=tag.name,
        kind=tag.kind,
        shared=tag.shared,
        affects_algorithm=tag.affects_algorithm,
        track_count=track_count,
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
        avg_level=event.avg_level,
        peak_level=event.peak_level,
        output_gain=event.output_gain,
        created_at=event.created_at.isoformat(),
    )


def apply_track_update(
    session: Session,
    track: Track,
    payload: TrackUpdate,
    owner_config_id: int | None = None,
) -> None:
    fields = payload.model_dump(exclude_unset=True)
    # Track metadata/groups/tags are SHARED content; an owned profile only edits its own ratings
    # and its own private favourite tag (handled below).
    if owner_config_id is None:
        for field in [
            "title",
            "artist",
            "album",
            "has_lyrics",
            "sub_group",
            "manual_multiplier",
            "clip_start_seconds",
            "clip_end_seconds",
            "audio_only",
            "is_original_rendition",
            "favourite",
        ]:
            if field in fields:
                setattr(track, field, fields[field])
        if payload.groups is not None:
            replace_groups(session, track, payload.groups)
        if payload.cooldown_tags is not None:
            replace_tags(session, track, payload.cooldown_tags)
        if payload.embeds is not None:
            replace_embeds(session, track, payload.embeds)
    elif "favourite" in fields:
        # Favourite is a per-user opinion: an owned profile writes it to its own link, never onto
        # the shared Track (which would leak its taste to everyone sharing the song).
        set_owner_favourite(session, owner_config_id, track.id, bool(fields["favourite"]))
    if payload.tags is None and "favourite" in fields:
        # A favourite-only write (older clients, curation flows) still keeps the tag in step.
        set_favourite_tag(session, track.id, bool(fields["favourite"]), owner_config_id)
    if payload.tags is not None:
        replace_track_tags(session, track, payload.tags, owner_config_id)
    if payload.ratings is not None:
        upsert_ratings(
            session,
            track,
            payload.ratings,
            session_id=payload.rating_session_id,
            owner_config_id=owner_config_id,
        )


def _resolve_embed(payload: EmbedWrite) -> tuple[str, str, float | None] | None:
    """Turn an embed write into (provider, external_id, start_seconds), parsing a bare URL when the
    provider/id aren't given directly. None if it isn't a URL we recognise."""
    if payload.provider and payload.external_id:
        # A directly-supplied id must be a well-formed id for its provider — never trust an
        # arbitrary string that would later reach a player. Fall back to URL parsing if not.
        if is_valid_external_id(payload.provider, payload.external_id):
            return payload.provider, payload.external_id, payload.start_seconds
    if payload.url:
        parsed = parse_embed_url(payload.url)
        if parsed is not None:
            start = payload.start_seconds
            if start is None:
                start = parsed.start_seconds
            return parsed.provider, parsed.external_id, start
    return None


def replace_embeds(session: Session, track: Track, embeds: list[EmbedWrite]) -> None:
    session.execute(delete(Embed).where(Embed.track_id == track.id))
    session.flush()
    for embed_payload in embeds:
        resolved = _resolve_embed(embed_payload)
        if resolved is None:
            continue
        provider, external_id, start_seconds = resolved
        session.add(
            Embed(
                track=track,
                provider=provider,
                external_id=external_id,
                url=embed_payload.url,
                start_seconds=start_seconds,
            )
        )


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


def replace_track_tags(
    session: Session, track: Track, tag_names: list[str], owner_config_id: int | None
) -> None:
    """Replace the track's tag assignments in the requesting scope. Every scope owns its own
    rows: a profile's removals never touch another profile's rows or local mode's (a shared tag
    just makes everyone's rows visible to all, so a shared assignment only disappears once every
    scope that added it has removed its own). Unknown names become cosmetic custom tags. The
    favourite boolean columns are kept in step so the algorithm and exports keep working
    unchanged."""
    wanted: list[str] = []
    seen: set[str] = set()
    for name in tag_names:
        cleaned = name.strip()[:120]
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            wanted.append(cleaned)
    tags_by_name = {tag.name: tag for tag in session.scalars(select(Tag))}
    for name in wanted:
        if name not in tags_by_name:
            tag = Tag(name=name, kind="custom")
            session.add(tag)
            session.flush()
            tags_by_name[name] = tag
    tag_by_id = {tag.id: tag for tag in tags_by_name.values()}
    rows = session.scalars(select(TrackTag).where(TrackTag.track_id == track.id)).all()
    existing: set[int] = set()
    for row in rows:
        tag = tag_by_id.get(row.tag_id)
        if tag is None:
            continue
        if row.owner_config_id != owner_config_id:
            continue  # another scope's contribution — never touched
        if tag.name in seen:
            existing.add(row.tag_id)
        else:
            session.delete(row)
    for name in wanted:
        tag = tags_by_name[name]
        if tag.id not in existing:
            session.add(
                TrackTag(track_id=track.id, tag_id=tag.id, owner_config_id=owner_config_id)
            )
    favourite = FAVOURITE_TAG_NAME in seen
    if owner_config_id is None:
        track.favourite = favourite
    else:
        set_owner_favourite(session, owner_config_id, track.id, favourite)


# One listen must never be double-counted: a re-rate within this window is treated as a
# correction of the previous mark and revises that sample in place. Only a later rating
# (a new listen / a changed mind) appends a fresh sample to the running history.
RATING_CORRECTION_WINDOW = timedelta(minutes=15)


def upsert_ratings(
    session: Session,
    track: Track,
    ratings: dict[str, float | None],
    session_id: str | None = None,
    owner_config_id: int | None = None,
) -> None:
    factor_map = {factor.key: factor for factor in session.scalars(select(RatingFactor))}
    for key, value in ratings.items():
        factor = factor_map.get(key)
        if factor is None:
            continue
        clamped = None if value is None else min(max(float(value), 0.0), 5.0)
        latest = session.scalar(
            select(RatingSample)
            .where(
                RatingSample.track_id == track.id,
                RatingSample.factor_id == factor.id,
                RatingSample.owner_config_id.is_(None)
                if owner_config_id is None
                else RatingSample.owner_config_id == owner_config_id,
            )
            .order_by(RatingSample.created_at.desc(), RatingSample.id.desc())
            .limit(1)
        )
        if owner_config_id is None:
            # Legacy/local: update the shared latest-star cache and compare against it.
            rating = session.scalar(
                select(TrackRating).where(
                    TrackRating.track_id == track.id,
                    TrackRating.factor_id == factor.id,
                )
            )
            previous = rating.value if rating is not None else None
            if rating is None:
                rating = TrackRating(track=track, factor=factor)
                session.add(rating)
            rating.value = clamped
        else:
            # Owned: ratings are private history only — never touch the shared TrackRating cache.
            # Change-detection compares against this profile's own most recent sample.
            previous = latest.value if latest is not None else None
        # Touch the append-only history ONLY on a genuine change, so the track
        # editor's "save all fields" can't spam duplicate samples for unchanged factors.
        if clamped == previous:
            continue
        latest_at = latest.created_at if latest is not None else None
        if latest_at is not None and latest_at.tzinfo is None:
            latest_at = latest_at.replace(tzinfo=UTC)
        if (
            latest is not None
            and latest.source == "user"
            and latest_at is not None
            and now_utc() - latest_at <= RATING_CORRECTION_WINDOW
        ):
            latest.value = clamped
        else:
            session.add(
                RatingSample(
                    track_id=track.id,
                    factor_id=factor.id,
                    value=clamped,
                    source="user",
                    session_id=session_id,
                    owner_config_id=owner_config_id,
                )
            )
