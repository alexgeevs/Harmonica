"""Pure organising for the YouTube video-list importer.

Turns fetched video metadata into proposed library tracks (stage one, always safe) and suggested
same-song clusters (stage two, always shown for the user to confirm and never applied on its own).
No I/O here, so it is straightforward to test. The proposed tracks use the same shape the library
import endpoint accepts, so they flow through the existing review-before-import screen unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from harmonica.embeds import YOUTUBE
from harmonica.youtube_import import VideoMeta

# Bracketed qualifiers and stock phrases stripped before parsing an artist and a title.
_BRACKETS_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
_NOISE_RE = re.compile(
    r"\b(official\s+(music\s+)?video|official\s+audio|official\s+visualizer|lyric[s]?"
    r"(\s+video)?|visualizer|audio|full\s+album|hd|hq|4k|mv)\b",
    re.IGNORECASE,
)
_VARIANT_RE = re.compile(
    r"\b(cover|live|remix|acoustic|remaster(?:ed)?|instrumental|karaoke|unplugged|demo|session|"
    r"reprise|edit|version)\b",
    re.IGNORECASE,
)
# Splits an "Artist - Title" video name. Hyphen, en dash, or em dash (videos use all three even
# though Harmonica's own copy does not).
_TITLE_SPLIT_RE = re.compile(r"\s+[-–—]\s+")
_TOPIC_SUFFIX_RE = re.compile(r"\s*-\s*topic$", re.IGNORECASE)
_MUSIC_CATEGORY_ID = "10"
# Anything longer than this (in seconds) is unlikely to be a single song. Used only to flag, never
# to drop: the user still sees and decides.
_LONG_SECONDS = 20 * 60


@dataclass(frozen=True)
class ClusterSuggestion:
    key: str
    suggested_sub_group: str
    song_ids: list[str]
    reason: str


@dataclass(frozen=True)
class VideoSummary:
    video_id: str
    title: str | None
    channel: str | None
    duration_seconds: int | None
    available: bool
    likely_song: bool


@dataclass(frozen=True)
class OrganizeResult:
    tracks: list[dict]
    clusters: list[ClusterSuggestion]
    videos: list[VideoSummary]


def _clean_channel(channel: str | None) -> str | None:
    if not channel:
        return None
    return _TOPIC_SUFFIX_RE.sub("", channel).strip() or None


def _strip_noise(text: str) -> str:
    text = _BRACKETS_RE.sub(" ", text)
    text = _NOISE_RE.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip(" -–—")


def _split_artist_title(raw_title: str) -> tuple[str | None, str]:
    """Best-effort split of a video title into (artist, title). Falls back to (None, cleaned)."""
    cleaned = _strip_noise(raw_title)
    parts = _TITLE_SPLIT_RE.split(cleaned, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return None, (cleaned or raw_title.strip())


def _normalise_words(text: str) -> list[str]:
    """Lowercased content words, with bracketed text, stock phrases, variant words, and punctuation
    stripped. Single characters are dropped so stray letters do not count."""
    text = _BRACKETS_RE.sub(" ", text)
    text = _NOISE_RE.sub(" ", text)
    text = _VARIANT_RE.sub(" ", text)
    text = re.sub(r"[^0-9a-zà-ɏ]+", " ", text.lower())
    return [word for word in text.split() if len(word) > 1]


def _signature(artist: str | None, title: str) -> str:
    """An order-insensitive identity for a song, so re-uploads that swap ``Artist - Title`` for
    ``Title - Artist`` still group. The words are de-duplicated and sorted."""
    words = _normalise_words(f"{artist or ''} {title}")
    return " ".join(sorted(set(words)))


def _proposed_track(meta: VideoMeta, factors: set[str]) -> dict:
    artist, title = _split_artist_title(meta.title or "")
    if "title" not in factors:
        artist, title = None, (meta.title or "").strip()
    channel = _clean_channel(meta.channel)
    groups: list[dict] = []
    if "channel" in factors and channel:
        groups.append({"name": channel, "group_type": "source", "share": None})
    return {
        "song_id": f"yt:{meta.video_id}",
        "title": title or (meta.title or "").strip() or meta.video_id,
        "artist": artist,
        "album": None,
        "has_lyrics": True,
        "sub_group": None,
        "manual_multiplier": 1.0,
        "groups": groups,
        "cooldown_tags": [],
        "ratings": {},
        "embeds": [
            {
                "provider": YOUTUBE,
                "external_id": meta.video_id,
                "url": f"https://www.youtube.com/watch?v={meta.video_id}",
                "start_seconds": None,
            }
        ],
    }


def _likely_song(meta: VideoMeta, factors: set[str]) -> bool:
    """A weak music/non-music hint from the Data API fields, when present. True when we have no
    reason to doubt it, so keyless imports (no duration or category) are treated as songs."""
    duration = meta.duration_seconds
    if "duration" in factors and duration is not None and duration > _LONG_SECONDS:
        return False
    if "category" in factors and meta.category_id and meta.category_id != _MUSIC_CATEGORY_ID:
        return False
    return True


def _build_clusters(
    entries: list[tuple[str, str, VideoMeta]], use_description: bool
) -> list[ClusterSuggestion]:
    """Stage two. Group proposed songs whose normalised identity matches (keyless). When the
    description factor is on, additionally pull a still-unclustered video into an existing cluster
    if that cluster's title appears in its description. Everything here is a suggestion the user
    still confirms, so a wrong grouping can never merge two songs on its own."""
    buckets: dict[str, dict] = {}
    for song_id, display, meta in entries:
        key = _signature(*_split_artist_title(meta.title or ""))
        if not key:
            continue
        bucket = buckets.setdefault(key, {"members": [], "display": display, "via_desc": False})
        bucket["members"].append(song_id)

    clustered = {sid for b in buckets.values() if len(b["members"]) >= 2 for sid in b["members"]}

    if use_description:
        # A video whose title does not match anyone can still be the same song if its description
        # names it. Any well-specified identity (three or more words) is a merge seed, even a lone
        # one, so an original and a differently-titled cover can pair. The word-set must be fully
        # contained in the description, which keeps a coincidental one or two word overlap out.
        seeds = {
            key: b for key, b in buckets.items() if b["members"] and len(key.split()) >= 3
        }
        for song_id, _display, meta in entries:
            if song_id in clustered or not meta.description:
                continue
            desc_tokens = set(_normalise_words(meta.description))
            for key, bucket in seeds.items():
                if song_id in bucket["members"] or not set(key.split()) <= desc_tokens:
                    continue
                bucket["members"].append(song_id)
                bucket["via_desc"] = True
                clustered.add(song_id)
                break

    suggestions: list[ClusterSuggestion] = []
    for key, bucket in buckets.items():
        if len(bucket["members"]) < 2:
            continue
        reason = f"{len(bucket['members'])} videos share a very similar title"
        if bucket["via_desc"]:
            reason += " (one matched via a description mention)"
        suggestions.append(
            ClusterSuggestion(
                key=key,
                suggested_sub_group=bucket["display"],
                song_ids=list(bucket["members"]),
                reason=reason,
            )
        )
    return suggestions


def organize(videos: list[VideoMeta], factors: set[str]) -> OrganizeResult:
    """Stage one: one proposed track per readable video. Stage two: suggested same-song clusters,
    returned separately so the caller can present them for confirmation before any sub-group is
    applied."""
    tracks: list[dict] = []
    summaries: list[VideoSummary] = []
    entries: list[tuple[str, str, VideoMeta]] = []
    for meta in videos:
        summaries.append(
            VideoSummary(
                video_id=meta.video_id,
                title=meta.title,
                channel=_clean_channel(meta.channel),
                duration_seconds=meta.duration_seconds,
                available=meta.available,
                likely_song=_likely_song(meta, factors) if meta.available else False,
            )
        )
        if not meta.available:
            continue
        track = _proposed_track(meta, factors)
        tracks.append(track)
        entries.append((track["song_id"], track["title"], meta))

    clusters = _build_clusters(entries, use_description="description" in factors)
    return OrganizeResult(tracks=tracks, clusters=clusters, videos=summaries)
