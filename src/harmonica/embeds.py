"""Optional third-party playback embeds (e.g. YouTube).

Off by default and opt-in. When a user enables embeds, playback of an embedded song uses the
provider's OFFICIAL player (for YouTube, the IFrame Player API). Harmonica never downloads,
scrapes, strips ads from, or extracts the audio track out of embedded content: those uses are
prohibited by the providers' terms. This module only recognises a link and records which video it
points at; the official player does the playing on the frontend.

Adding a provider is deliberately small: write a ``parse_*`` function that turns a URL into a
``ParsedEmbed`` and register it in ``_PARSERS``, then add a player for it on the frontend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

YOUTUBE = "youtube"

# Hosts we treat as YouTube. music.youtube.com is included because it is still the same IFrame
# player and the same video ids — we are not doing anything audio-only or music-specific with it.
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_DURATION_RE = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")


@dataclass(frozen=True)
class ParsedEmbed:
    provider: str
    external_id: str
    # Official start offset in seconds (the provider's supported start=/t= parameter). Trimming an
    # intro this way is a first-class player feature, not a modification of the content.
    start_seconds: float | None


def _duration_to_seconds(raw: str) -> float | None:
    raw = raw.strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    match = _DURATION_RE.fullmatch(raw)
    if match is None or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(group) if group else 0 for group in match.groups())
    return float(hours * 3600 + minutes * 60 + seconds)


def _parse_start(query: dict[str, list[str]]) -> float | None:
    for key in ("start", "t"):
        values = query.get(key)
        if values:
            seconds = _duration_to_seconds(values[0])
            if seconds is not None:
                return seconds
    return None


def parse_youtube_url(url: str) -> ParsedEmbed | None:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return None
    query = parse_qs(parsed.query)
    video_id: str | None = None
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.lstrip("/").split("/", 1)[0] or None
    elif parsed.path == "/watch":
        values = query.get("v")
        video_id = values[0] if values else None
    elif parsed.path.startswith(("/embed/", "/v/", "/shorts/", "/live/")):
        parts = parsed.path.split("/")
        video_id = parts[2] if len(parts) > 2 else None
    if not video_id or not _VIDEO_ID_RE.match(video_id):
        return None
    return ParsedEmbed(provider=YOUTUBE, external_id=video_id, start_seconds=_parse_start(query))


_PARSERS = {YOUTUBE: parse_youtube_url}


def parse_embed_url(url: str) -> ParsedEmbed | None:
    """Recognise a media URL as a provider embed, or None if no provider matches."""
    if not url:
        return None
    for parser in _PARSERS.values():
        parsed = parser(url)
        if parsed is not None:
            return parsed
    return None


def known_providers() -> tuple[str, ...]:
    return tuple(_PARSERS)
