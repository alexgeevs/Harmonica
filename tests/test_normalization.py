from __future__ import annotations

import math

from fastapi.testclient import TestClient
from sqlalchemy import select

from harmonica.api import create_app
from harmonica.config import Settings
from harmonica.db import SessionLocal
from harmonica.models import Track
from harmonica.normalization import (
    FactorStats,
    compute_factor_stats,
    pooled_within_series_sd,
    series_effective,
    series_values,
    song_overall,
)


class _Factor:
    def __init__(self, fid: int, key: str) -> None:
        self.id = fid
        self.key = key


def _ready_stats(mu: float, sigma: float, alpha: float = 1.0) -> FactorStats:
    return FactorStats(
        factor_id=1, key="overall", mu=mu, sigma=sigma, coverage=1.0,
        n_samples=99, n_multi_rated_songs=99, ready=True, alpha=alpha,
    )


def test_series_values_resets_on_retract() -> None:
    # latest retract => empty; values after the last NULL survive.
    assert series_values([4.0, None, 3.0, 2.0]) == [3.0, 2.0]
    assert series_values([4.0, 3.0, None]) == []
    assert series_values([]) == []


def test_pooled_within_series_sd_recovers_within_not_total() -> None:
    # Two songs, each rated tightly around very different means. The WITHIN-song spread is
    # tiny; the BETWEEN-song spread is huge. Pooled within-series SD must report the small one.
    song_a = [1.0, 1.0, 1.0]  # mean 1, within-var 0
    song_b = [5.0, 5.0, 5.0]  # mean 5, within-var 0
    assert pooled_within_series_sd([song_a, song_b]) == 0.0
    # Add a little within-song wobble: each varies by ±1 around its own mean.
    song_a2 = [0.0, 2.0]  # mean 1, sum sq dev = 2
    song_b2 = [4.0, 6.0]  # mean 5, sum sq dev = 2
    # pooled = sqrt((2+2)/(1+1)) = sqrt(2) ~ 1.414  (NOT the ~2.0+ total SD across all four)
    assert math.isclose(pooled_within_series_sd([song_a2, song_b2]), math.sqrt(2.0))


def test_series_effective_unready_is_plain_mean() -> None:
    settings = Settings()
    unready = FactorStats(1, "overall", mu=2.5, sigma=1.0, coverage=0.1,
                          n_samples=2, n_multi_rated_songs=0, ready=False, alpha=0.0)
    assert series_effective([2.0, 4.0], unready, settings) == 3.0
    assert series_effective([], unready, settings) is None


def test_series_effective_single_rating_shrinks_halfway() -> None:
    # n=1, pseudocount 1 => B = 0.5: a lone rating is pulled halfway to the library mean.
    settings = Settings(rating_shrinkage_pseudocount=1.0)
    stats = _ready_stats(mu=2.0, sigma=1.0)
    # winsorise no-op at n=1 (=4.0); shrink: 2.0 + 0.5*(4.0-2.0) = 3.0; alpha=1 => 3.0
    assert math.isclose(series_effective([4.0], stats, settings), 3.0)


def test_series_effective_winsorises_outlier() -> None:
    settings = Settings(rating_outlier_sd=1.0, rating_shrinkage_pseudocount=0.0)
    stats = _ready_stats(mu=3.0, sigma=1.0)
    # series mean = (3+3+3+3+5)/5 = 3.4; bound = 1.0 => the 5.0 is clipped to 4.4.
    # winsorised mean = (3+3+3+3+4.4)/5 = 3.28; pseudocount 0 => B=1 => normalised 3.28.
    got = series_effective([3.0, 3.0, 3.0, 3.0, 5.0], stats, settings)
    assert math.isclose(got, 3.28)


def test_song_overall_is_50_50_with_no_double_count() -> None:
    # overall present + others present => exactly 0.5*direct + 0.5*mean(others).
    eff = {"overall": 4.0, "lyrics": 2.0, "music": 4.0, "performance": 1.0}
    applicable = {"overall", "lyrics", "music", "performance"}
    # others mean = (2+4)/2 = 3 (performance EXCLUDED); overall = 0.5*4 + 0.5*3 = 3.5
    assert song_overall(eff, applicable) == 3.5
    # only direct
    assert song_overall({"overall": 4.0}, {"overall"}) == 4.0
    # only others
    assert song_overall({"lyrics": 2.0, "music": 4.0}, {"lyrics", "music"}) == 3.0
    # neither
    assert song_overall({}, set()) is None


def test_song_overall_excludes_performance_from_others() -> None:
    # Performance must never inflate the shared song rating.
    with_perf = song_overall({"lyrics": 2.0, "performance": 5.0}, {"lyrics", "performance"})
    assert with_perf == 2.0


def test_compute_factor_stats_readiness_gate() -> None:
    # Below the coverage/depth thresholds => not ready (normalisation stays inert).
    settings = Settings()
    series = {1: [3.0, 4.0], 2: [2.0]}  # only 1 multi-rated song, 3 samples
    stats = compute_factor_stats(_Factor(1, "overall"), series, 10, settings)
    assert stats.ready is False
    assert math.isclose(stats.coverage, 0.2)


def test_normalised_overall_drives_generation_multiplier() -> None:
    # End-to-end: a high-rated song is boosted, a low-rated song suppressed, unrated neutral,
    # via the new normalisation path (50/50 overall) feeding rating_multiplier.
    with TestClient(create_app()) as client:
        with SessionLocal() as session:
            for i in range(4):
                session.add(Track(song_id=f"norm_e2e_{i}", title=f"Norm {i}"))
            session.commit()
            ids = [
                t.id
                for t in session.scalars(select(Track))
                if t.song_id.startswith("norm_e2e_")
            ]
        client.patch(f"/tracks/{ids[0]}", json={"ratings": {"overall": 5, "music": 5}})
        client.patch(f"/tracks/{ids[1]}", json={"ratings": {"overall": 1, "music": 1}})
        run = client.post(
            "/queue/generate", json={"length": 60, "explain": True, "ui_active": True}
        ).json()
        mult = {}
        for item in run["items"]:
            mult.setdefault(item["track"]["id"], item["explanation"]["rating_multiplier"])
        assert mult[ids[0]] > 1.0 > mult[ids[1]]
        assert math.isclose(mult[ids[2]], 1.0)
