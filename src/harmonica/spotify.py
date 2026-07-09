"""Optional read-only Spotify integration.

Off by default and opt-in. When enabled with app credentials, Harmonica reads the track list of a
public Spotify playlist through Spotify's official Web API. This is METADATA ONLY: track names,
artists, album, and duration, used to compare a playlist against your own library. It never
downloads audio, scrapes pages, or touches Spotify playback, which the Web API does not offer and
Spotify's terms prohibit.

App credentials (client id + secret) are user secrets handled exactly like the YouTube key: read
from an env var or a private file under the Harmonica home, never stored in the DB, exported,
logged, or sent to the browser. Every Spotify request is made server-side, so the secret and the
access token never reach the client. The only user-controlled input is a playlist id, which is
validated against a strict character set before being placed into a request to a fixed Spotify
host. There is no way to point these requests at an arbitrary URL, and redirects are refused, so
this cannot be used to reach an internal service (no SSRF).
"""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# A Spotify id is base62. Keep the accepted set strict so a parsed id can only ever be inserted
# into a fixed-host URL, never used to smuggle a path or a different host.
_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9]{1,40}$")
_ALLOWED_HOSTS = {"api.spotify.com", "accounts.spotify.com"}

_PAGE_LIMIT = 100
_MAX_TRACKS = 500
_TIMEOUT_SECONDS = 10.0
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# Fields we ask Spotify to return, so responses stay small and we only ever read metadata.
_TRACK_FIELDS = (
    "items(track(name,artists(name),album(name),duration_ms,id,external_urls(spotify)))"
)


class SpotifyError(Exception):
    """A user-facing Spotify failure (bad input, auth, or upstream). The message is always safe to
    show: it never contains the client secret or the access token."""


@dataclass(frozen=True)
class SpotifyTrack:
    name: str
    artists: list[str]
    album: str | None
    duration_ms: int | None
    spotify_id: str | None
    url: str | None


@dataclass(frozen=True)
class SpotifyPlaylist:
    id: str
    name: str | None
    tracks: list[SpotifyTrack]
    # True when the playlist has more tracks than we fetched (capped for safety).
    truncated: bool


class Transport(Protocol):
    """The one place real network I/O happens. Injectable so tests never hit Spotify."""

    def post_form(self, url: str, data: dict[str, str], headers: dict[str, str]) -> dict: ...

    def get_json(self, url: str, headers: dict[str, str]) -> dict: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects outright. Spotify's API does not redirect these calls, and refusing means a
    compromised or unexpected response can't bounce us to an internal address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, D401
        raise SpotifyError("Spotify returned an unexpected redirect")


class UrllibTransport:
    """Default transport over the standard library (no third-party HTTP dependency)."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect())

    def _open(self, request: urllib.request.Request) -> dict:
        _assert_allowed(request.full_url)
        try:
            with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:  # 4xx/5xx from Spotify
            raise SpotifyError(_status_message(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SpotifyError("Could not reach Spotify") from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise SpotifyError("Spotify response was unexpectedly large")
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SpotifyError("Spotify sent a response we could not read") from exc

    def post_form(self, url: str, data: dict[str, str], headers: dict[str, str]) -> dict:
        body = urllib.parse.urlencode(data).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        return self._open(request)

    def get_json(self, url: str, headers: dict[str, str]) -> dict:
        request = urllib.request.Request(url, headers=headers, method="GET")
        return self._open(request)


def _assert_allowed(url: str) -> None:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        # Defence in depth: even though we only ever build URLs from fixed hosts, never open one
        # that isn't a known Spotify endpoint.
        raise SpotifyError("Refusing to contact a non-Spotify host")


def _status_message(code: int) -> str:
    if code in (401, 403):
        return "Spotify rejected the app credentials"
    if code == 404:
        return "That Spotify playlist was not found (it may be private)"
    if code == 429:
        return "Spotify is rate-limiting requests; try again shortly"
    return "Spotify returned an error"


def parse_playlist_id(value: str) -> str | None:
    """Extract a playlist id from a URL, a ``spotify:playlist:`` URI, or a bare id. None if it is
    not a well-formed id."""
    value = (value or "").strip()
    if not value:
        return None
    candidate = value
    if value.startswith("spotify:"):
        candidate = value.split(":")[-1]
    elif "://" in value or "open.spotify.com" in value:
        parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
        segments = [segment for segment in parsed.path.split("/") if segment]
        candidate = ""
        for index, segment in enumerate(segments):
            if segment == "playlist" and index + 1 < len(segments):
                candidate = segments[index + 1]
                break
    candidate = candidate.split("?")[0]
    return candidate if _PLAYLIST_ID_RE.match(candidate) else None


# App access token cache, keyed by client id, so we don't re-authenticate on every request.
_token_cache: dict[str, tuple[str, float]] = {}


def clear_token_cache() -> None:
    _token_cache.clear()


def _get_app_token(client_id: str, client_secret: str, transport: Transport) -> str:
    cached = _token_cache.get(client_id)
    if cached and cached[1] - 30 > time.time():
        return cached[0]
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
    payload = transport.post_form(
        TOKEN_URL,
        {"grant_type": "client_credentials"},
        {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    token = payload.get("access_token")
    if not token:
        raise SpotifyError("Spotify did not return an access token")
    expires_in = float(payload.get("expires_in", 3600))
    _token_cache[client_id] = (token, time.time() + expires_in)
    return token


def _normalise_track(raw: dict | None) -> SpotifyTrack | None:
    # Local files, removed tracks, and podcast episodes come back as null or without a name.
    if not raw or not raw.get("name"):
        return None
    artists = [a.get("name", "") for a in raw.get("artists", []) if a.get("name")]
    album = (raw.get("album") or {}).get("name")
    return SpotifyTrack(
        name=raw["name"],
        artists=artists,
        album=album,
        duration_ms=raw.get("duration_ms"),
        spotify_id=raw.get("id"),
        url=(raw.get("external_urls") or {}).get("spotify"),
    )


def fetch_playlist(
    client_id: str,
    client_secret: str,
    playlist_ref: str,
    *,
    transport: Transport | None = None,
) -> SpotifyPlaylist:
    """Read a public playlist's track metadata. Raises SpotifyError for bad input or upstream
    failures; the raised message is always safe to surface to the user."""
    transport = transport or UrllibTransport()
    playlist_id = parse_playlist_id(playlist_ref)
    if playlist_id is None:
        raise SpotifyError("That does not look like a Spotify playlist link")

    token = _get_app_token(client_id, client_secret, transport)
    auth = {"Authorization": f"Bearer {token}"}

    name_payload = transport.get_json(
        f"{API_BASE}/playlists/{playlist_id}?fields=name", auth
    )
    name = name_payload.get("name")

    tracks: list[SpotifyTrack] = []
    truncated = False
    offset = 0
    while True:
        # We paginate with our own offset against the fixed host rather than following Spotify's
        # `next` URL, so we never fetch a URL handed to us in a response.
        query = urllib.parse.urlencode(
            {"limit": _PAGE_LIMIT, "offset": offset, "fields": f"{_TRACK_FIELDS},total"}
        )
        page = transport.get_json(f"{API_BASE}/playlists/{playlist_id}/tracks?{query}", auth)
        items = page.get("items") or []
        for item in items:
            track = _normalise_track(item.get("track"))
            if track is not None:
                tracks.append(track)
            if len(tracks) >= _MAX_TRACKS:
                truncated = True
                break
        if truncated or len(items) < _PAGE_LIMIT:
            break
        offset += _PAGE_LIMIT

    return SpotifyPlaylist(id=playlist_id, name=name, tracks=tracks, truncated=truncated)
