from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_harmonica_home() -> Path:
    return Path(os.environ.get("HARMONICA_HOME", ".harmonica")).expanduser().resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HARMONICA_", env_file=".env", extra="ignore")

    app_name: str = "Harmonica"
    home: Path = Field(default_factory=default_harmonica_home)
    database_url: str | None = None
    media_root: Path | None = None
    log_dir: Path | None = None
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
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.home / 'harmonica.db'}"

    @property
    def logs_path(self) -> Path:
        return self.log_dir or self.home / "logs"

    def ensure_dirs(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
