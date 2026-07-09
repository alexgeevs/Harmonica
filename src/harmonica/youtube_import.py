"""Optional read-only YouTube metadata lookups for the video-list importer.

Off by default and gated behind ``youtube_embed_enabled``. Given a list of video links the user has
chosen to import, this reads each video's PUBLIC metadata so the importer can organise them into
tracks. Two sources, picked by which factors the user selected:

- oEmbed (``https://www.youtube.com/oembed``): keyless and official. Title, channel, thumbnail.
- Data API v3 ``videos.list``: needs the user's own Data API key. Adds duration, description, tags,
  category, and publish date. Batched 50 ids per call.

METADATA ONLY. No audio, no page scraping, no caption download (caption text is not available for
third-party videos), and no ad interaction. Playback is still YouTube's official IFrame player on
the frontend. Every request is made server-side to a fixed host, redirects are refused, and
responses are size and time capped, mirroring ``spotify.py``, so a pasted link can never be turned
into a request to an arbitrary or internal host (no SSRF). The Data API key is sent in an
``X-goog-api-key`` header, never in a URL, so it cannot leak through a log line or a traceback.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from harmonica.embeds import parse_youtube_url

OEMBED_URL = "https://www.youtube.com/oembed"
DATA_API_URL = "https://www.googleapis.com/youtube/v3/videos"
_ALLOWED_HOSTS = {"www.youtube.com", "youtube.com", "www.googleapis.com"}

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# The factors the picker offers. Keyless ones come from oEmbed; the rest need the Data API. Kept
# here as the authoritative set so the endpoint can validate a request and decide the fetch path.
KEYLESS_FACTORS = ("channel", "title")
KEY_REQUIRED_FACTORS = ("duration", "description", "category", "tags", "published")
KNOWN_FACTORS = frozenset(KEYLESS_FACTORS + KEY_REQUIRED_FACTORS)

# Caps. oEmbed is one request per video, so a smaller ceiling; the Data API batches 50 ids a call.
MAX_VIDEOS_KEYLESS = 100
MAX_VIDEOS = 500
_DATA_API_BATCH = 50
_TIMEOUT_SECONDS = 10.0
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class YouTubeImportError(Exception):
    """A user-facing import failure. The message is always safe to show: it never contains the
    Data API key (which is only ever sent as a request header, never built into a URL)."""


@dataclass(frozen=True)
class VideoMeta:
    video_id: str
    # None when the video could not be read (private, deleted, or embedding disabled).
    title: str | None = None
    channel: str | None = None
    duration_seconds: int | None = None
    description: str | None = None
    published_at: str | None = None
    category_id: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def available(self) -> bool:
        return self.title is not None


class Transport(Protocol):
    """The one place real network I/O happens. Injectable so tests never hit YouTube."""

    def get_json(self, url: str, headers: dict[str, str]) -> dict: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects outright, so an unexpected response cannot bounce us to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, D401
        raise YouTubeImportError("YouTube returned an unexpected redirect")


class UrllibTransport:
    """Default transport over the standard library (no third-party HTTP dependency)."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect())

    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        _assert_allowed(url)
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:  # 4xx/5xx from YouTube
            raise YouTubeImportError(_status_message(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise YouTubeImportError("Could not reach YouTube") from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise YouTubeImportError("YouTube sent an unexpectedly large response")
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise YouTubeImportError("YouTube sent a response we could not read") from exc


def _assert_allowed(url: str) -> None:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        # Defence in depth: even though URLs are only ever built from fixed hosts, never open one
        # that is not a known YouTube endpoint.
        raise YouTubeImportError("Refusing to contact a non-YouTube host")


def _status_message(code: int) -> str:
    if code in (401, 403):
        return "YouTube rejected the request (check the Data API key if you set one)"
    if code == 404:
        return "A video was not found"
    if code == 429:
        return "YouTube is rate-limiting requests; try again shortly"
    return "YouTube returned an error"


def requires_api_key(factors: set[str]) -> bool:
    """Whether the chosen factors need the Data API (so the caller can prompt for a key)."""
    return any(factor in KEY_REQUIRED_FACTORS for factor in factors)


def normalise_factors(factors: list[str]) -> set[str]:
    """Keep only recognised factors; always include the two keyless basics the importer relies on
    (a title and who uploaded it), so stage-one organising can always run."""
    chosen = {factor for factor in factors if factor in KNOWN_FACTORS}
    chosen.update(KEYLESS_FACTORS)
    return chosen


def extract_video_ids(text: str) -> list[str]:
    """Pull YouTube video ids out of a pasted blob of links (and bare ids), de-duplicated and in the
    order first seen. Anything that is not a recognisable video link or id is ignored."""
    ids: list[str] = []
    seen: set[str] = set()
    for token in re.split(r"[\s,;]+", text or ""):
        token = token.strip()
        if not token:
            continue
        parsed = parse_youtube_url(token)
        video_id = parsed.external_id if parsed else (token if _VIDEO_ID_RE.match(token) else None)
        if video_id and video_id not in seen:
            seen.add(video_id)
            ids.append(video_id)
    return ids


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def fetch_via_oembed(
    video_ids: list[str], *, transport: Transport | None = None
) -> list[VideoMeta]:
    """Keyless path: read each video's title and channel from YouTube's official oEmbed endpoint. A
    video that cannot be read (private, deleted, embedding disabled) comes back unavailable rather
    than failing the whole import. Raises only if every video fails."""
    transport = transport or UrllibTransport()
    metas: list[VideoMeta] = []
    resolved = 0
    for video_id in video_ids:
        query = urllib.parse.urlencode({"url": _watch_url(video_id), "format": "json"})
        try:
            payload = transport.get_json(f"{OEMBED_URL}?{query}", {})
        except YouTubeImportError:
            metas.append(VideoMeta(video_id=video_id))
            continue
        title = (payload.get("title") or "").strip() or None
        channel = (payload.get("author_name") or "").strip() or None
        metas.append(VideoMeta(video_id=video_id, title=title, channel=channel))
        if title:
            resolved += 1
    if video_ids and resolved == 0:
        raise YouTubeImportError("Could not read any of those videos from YouTube")
    return metas


def _parse_iso8601_duration(raw: str | None) -> int | None:
    """ISO 8601 like ``PT4M13S`` to whole seconds. None for anything unparseable."""
    if not raw:
        return None
    match = re.fullmatch(
        r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", raw
    )
    if match is None or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(group) if group else 0 for group in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _meta_from_api_item(item: dict) -> VideoMeta | None:
    video_id = item.get("id")
    if not isinstance(video_id, str) or not _VIDEO_ID_RE.match(video_id):
        return None
    snippet = item.get("snippet") or {}
    content = item.get("contentDetails") or {}
    tags = tuple(t for t in (snippet.get("tags") or []) if isinstance(t, str))[:40]
    return VideoMeta(
        video_id=video_id,
        title=(snippet.get("title") or "").strip() or None,
        channel=(snippet.get("channelTitle") or "").strip() or None,
        duration_seconds=_parse_iso8601_duration(content.get("duration")),
        description=(snippet.get("description") or "").strip() or None,
        published_at=snippet.get("publishedAt"),
        category_id=snippet.get("categoryId"),
        tags=tags,
    )


def fetch_via_data_api(
    video_ids: list[str], api_key: str, *, transport: Transport | None = None
) -> list[VideoMeta]:
    """Keyed path: read richer metadata through the Data API, 50 ids per call. Videos that are
    missing from a response (private or deleted) come back unavailable. The key is sent as an
    ``X-goog-api-key`` header, so it is never placed in a URL."""
    transport = transport or UrllibTransport()
    headers = {"X-goog-api-key": api_key}
    by_id: dict[str, VideoMeta] = {}
    for start in range(0, len(video_ids), _DATA_API_BATCH):
        batch = video_ids[start : start + _DATA_API_BATCH]
        query = urllib.parse.urlencode(
            {"part": "snippet,contentDetails", "id": ",".join(batch), "maxResults": _DATA_API_BATCH}
        )
        payload = transport.get_json(f"{DATA_API_URL}?{query}", headers)
        for item in payload.get("items") or []:
            meta = _meta_from_api_item(item)
            if meta is not None:
                by_id[meta.video_id] = meta
    # Preserve the paste order; unresolved ids come back unavailable.
    return [by_id.get(video_id, VideoMeta(video_id=video_id)) for video_id in video_ids]
