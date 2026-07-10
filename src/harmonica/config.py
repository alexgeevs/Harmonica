from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_harmonica_home() -> Path:
    return Path(os.environ.get("HARMONICA_HOME", ".harmonica")).expanduser().resolve()


def _restrict_permissions(path: Path) -> None:
    """Best-effort chmod 0600 on a secret file we create, so it isn't world/group readable. A
    no-op on platforms without POSIX permissions."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def path_within_root(candidate: str | Path, root: Path) -> Path | None:
    """Resolve ``candidate`` (following symlinks, normalising ``..``) and return it
    only if it stays inside ``root``; otherwise ``None``.

    The single guard against path traversal and symlink escape when serving or
    scanning media. ``root`` is expected to already be resolved.
    """
    try:
        resolved = Path(candidate).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved if resolved.is_relative_to(root) else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HARMONICA_", env_file=".env", extra="ignore")

    app_name: str = "Harmonica"
    home: Path = Field(default_factory=default_harmonica_home)
    database_url: str | None = None
    media_root: Path | None = None
    log_dir: Path | None = None
    # HMAC secret for signing per-profile auth tokens. If unset, a random key is generated once
    # and persisted under the Harmonica home so tokens survive restarts.
    secret_key: str | None = None
    # Force the authenticated access model on (True) or off (False). Unset (None) derives it from
    # the bind host: loopback = trusting local mode (no auth), anything else (0.0.0.0 / a LAN IP) =
    # exposed mode, where every non-public endpoint needs a valid profile token. Env
    # HARMONICA_REQUIRE_AUTH.
    require_auth: bool | None = None
    # Built web UI to serve from the daemon itself (so "run the daemon, open the bound URL" is the
    # whole app — identical locally on 127.0.0.1 and on a NAS over the LAN). Defaults to the repo's
    # web/dist when present; override for a packaged/Docker layout. Absent → daemon is API-only.
    web_dist: Path | None = None

    @property
    def effective_web_dist(self) -> Path | None:
        if self.web_dist is not None:
            return self.web_dist.expanduser().resolve()
        default = Path(__file__).resolve().parents[2] / "web" / "dist"
        return default if default.is_dir() else None
    host: str = "127.0.0.1"
    port: int = 8765

    beta: float = 1.25
    group_cooldown_floor: float = 0.05
    sub_group_cooldown_floor: float = 0.01
    default_playlist_length: int = 100
    song_rating_min_multiplier: float = 0.5
    song_rating_max_multiplier: float = 2.0
    group_rating_min_multiplier: float = 0.7
    group_rating_max_multiplier: float = 1.4
    enable_group_rating_multiplier: bool = True
    history_influence_enabled: bool = True
    skip_penalty_strength: float = 0.25
    # Skip penalty decays with recency (in events) so one old/accidental skip doesn't punish a
    # song forever and later completions recover it.
    skip_penalty_halflife: float = 30.0
    cold_start_enabled: bool = True
    cold_start_unrated_boost: float = 2.0
    visual_priority_enabled: bool = True
    visual_priority_multiplier: float = 1.35
    group_clustering_bias: float = 0.0
    # Satiation: pace a recently over-played song so a binge doesn't burn it out (recovers over
    # weeks). Rediscovery: resurface a dormant favourite the longer it's gone unheard.
    satiation_enabled: bool = True
    satiation_strength: float = 0.5
    satiation_window_days: float = 14.0
    satiation_floor: float = 0.3
    rediscovery_enabled: bool = True
    rediscovery_strength: float = 0.4
    rediscovery_halflife_days: float = 60.0
    # Optional stronger pacing for songs the user has tagged as favourites. Off by default (no
    # effect); when on, favourites get their satiation/rediscovery pacing amplified by the strength.
    favourite_pacing_enabled: bool = False
    favourite_pacing_strength: float = 1.5
    # Optional YouTube embed playback. Off by default and opt-in. When on, the frontend plays a song
    # that has a YouTube embed through YouTube's OFFICIAL IFrame player (which sets its own cookies,
    # hence the consent gate). Compliant use only: no audio-only extraction, ad-stripping, or
    # scraping. See src/harmonica/embeds.py.
    youtube_embed_enabled: bool = False
    # YouTube Data API key for OPTIONAL metadata lookups only (embedding itself needs no key). This
    # is a user secret: read from the env var or a private file under the Harmonica home, never
    # stored in the DB, never included in an export, never sent to the browser. See
    # effective_youtube_data_api_key(). Agents are instructed not to read it (AGENTS.md).
    youtube_data_api_key: str | None = None
    # Optional read-only Spotify playlist import. Off by default and opt-in. When on with app
    # credentials, the daemon reads a public playlist's track metadata via Spotify's Web API. No
    # audio, no scraping, no playback. See src/harmonica/spotify.py.
    spotify_enabled: bool = False
    # Spotify app credentials (client id + secret). Both are user secrets handled exactly like the
    # YouTube key: read from an env var or a private file under the Harmonica home, never stored in
    # the DB, exported, logged, or sent to the browser. Every Spotify call is server-side.
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    # Whether the create-profile form may list the library's songs for picking a subset. Off by
    # default so that, on a shared or networked install, creating a profile does not reveal which
    # songs exist. With it off, new profiles simply include all songs.
    profile_song_picker_enabled: bool = False
    # Hearing health & compression awareness.
    avoid_consecutive_compressed: bool = True
    compressed_break_reminder: bool = True
    loudness_warning_enabled: bool = True
    # Cautious by default: warnings should err toward firing early.
    loudness_warning_level: float = 0.55

    # Rating normalisation (Feature 1; docs/planning/rating-normalization-and-covers.md).
    rating_normalization_enabled: bool = True
    rating_outlier_sd: float = 1.0
    rating_session_mood_correction: bool = True
    rating_session_min_songs: int = 10
    rating_coverage_ready_fraction: float = 0.6
    # Per-user scale calibration: recentre so the user's OWN average maps to neutral and their
    # used range is stretched (e.g. a 4★-everything rater has their 4 treated as mediocre).
    rating_calibration_enabled: bool = True
    # Internal estimator constants (not exposed as user controls).
    rating_shrinkage_pseudocount: float = 1.0
    rating_min_multi_rated_songs: int = 20
    rating_min_samples_for_sd: int = 30
    rating_session_bias_min_sd: float = 0.5
    rating_session_bias_pseudocount: float = 10.0
    rating_calibration_min_rated_songs: int = 20
    rating_calibration_z_cap: float = 2.0

    # Show the full multiplier-by-multiplier maths behind "why this song" (off by default; the
    # plain-language reasons are always shown, this just adds the formula and the numbers).
    why_show_math: bool = False

    # Two-level cover selection (Feature 2 / Phase C). Off by default: when enabled the queue
    # first picks a song, then picks which rendition (cover) of it to play, with cover-count
    # boosting a song's chance logarithmically. See rating-normalization-and-covers.md.
    cover_two_level_enabled: bool = False
    cover_count_log_base: float = 4.0
    cover_original_bonus: float = 0.1
    # Bradley-Terry within-set "performance" (Phase D): bounded multiplier picking WHICH rendition,
    # derived from A/B verdicts. gamma scales log-strength → ratio; the prior shrinks thin evidence.
    cover_perf_min_multiplier: float = 0.7
    cover_perf_max_multiplier: float = 1.4
    cover_perf_gamma: float = 1.0
    cover_bt_prior_strength: float = 1.0
    # A/B comparison UX (Phase E). Eligible only when a set has >= min_covers renditions and the
    # listener is "active" (>= active_min_rated of the last active_window songs got a rating). The
    # set settles (stops prompting) once well-separated or a hard ceiling of verdicts is reached.
    cover_comparison_enabled: bool = True
    cover_comparison_min_covers: int = 4
    cover_comparison_cooldown_songs: int = 3
    cover_comparison_min_per_cover: int = 3
    cover_comparison_max_total: int = 40
    cover_comparison_settle_gap: float = 0.2
    cover_active_window: int = 5
    cover_active_min_rated: int = 4

    @property
    def effective_media_root(self) -> Path:
        """Root directory that every servable / scannable media file must stay within.

        Defaults to ``Storage`` relative to the working directory (matching the
        importer's layout); override with ``HARMONICA_MEDIA_ROOT`` — e.g. the mounted
        volume inside the NAS Docker container. This is the boundary that stops a
        crafted ``file_path`` (from an imported library or a scan) being read off disk.
        """
        root = self.media_root if self.media_root is not None else Path("Storage")
        return root.expanduser().resolve()

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.home / 'harmonica.db'}"

    @property
    def logs_path(self) -> Path:
        return self.log_dir or self.home / "logs"

    def is_loopback_host(self) -> bool:
        """True when the daemon is bound only to the local machine (no other device reaches it)."""
        return self.host in {"127.0.0.1", "localhost", "::1", ""}

    def auth_required(self) -> bool:
        """Whether the authenticated access model is enforced. Explicit ``require_auth`` wins;
        otherwise it turns on automatically whenever the daemon is bound off loopback (e.g. a NAS
        on 0.0.0.0), because that is when other devices can reach it and profile privacy matters."""
        if self.require_auth is not None:
            return self.require_auth
        return not self.is_loopback_host()

    def effective_secret_key(self) -> str:
        """The HMAC secret for signing profile tokens. Uses ``secret_key`` if set, else a random
        key generated once and persisted to ``home/secret.key`` (so tokens survive restarts).

        Rotating this file (deleting it, or changing ``secret_key``) invalidates every issued token
        at once — the intended way to revoke access to all profiles."""
        if self.secret_key:
            return self.secret_key
        key_path = self.home / "secret.key"
        if key_path.exists():
            return key_path.read_text(encoding="utf-8").strip()
        value = secrets.token_hex(32)
        self.home.mkdir(parents=True, exist_ok=True)
        key_path.write_text(value, encoding="utf-8")
        _restrict_permissions(key_path)
        return value

    def effective_youtube_data_api_key(self) -> str | None:
        """The user's YouTube Data API key, if configured: from the env var or a private key file
        under the Harmonica home. Returns None when absent. This value is never logged, exported, or
        sent to the browser, and agents are told not to read it — only its presence is ever exposed.
        """
        if self.youtube_data_api_key:
            return self.youtube_data_api_key
        key_path = self.home / "youtube_data_api.key"
        if key_path.exists():
            value = key_path.read_text(encoding="utf-8").strip()
            return value or None
        return None

    def _secret_from_env_or_file(self, value: str | None, filename: str) -> str | None:
        """A user secret: the configured value if set, else a private file under the home. Shared
        handling for the Spotify credentials, mirroring effective_youtube_data_api_key()."""
        if value:
            return value
        key_path = self.home / filename
        if key_path.exists():
            text = key_path.read_text(encoding="utf-8").strip()
            return text or None
        return None

    def effective_spotify_client_id(self) -> str | None:
        return self._secret_from_env_or_file(self.spotify_client_id, "spotify_client_id.key")

    def effective_spotify_client_secret(self) -> str | None:
        return self._secret_from_env_or_file(
            self.spotify_client_secret, "spotify_client_secret.key"
        )

    def spotify_credentials(self) -> tuple[str, str] | None:
        """Both credentials, or None if either is missing. Never logged or sent to the client."""
        client_id = self.effective_spotify_client_id()
        client_secret = self.effective_spotify_client_secret()
        if client_id and client_secret:
            return client_id, client_secret
        return None

    def ensure_dirs(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
