from __future__ import annotations

from harmonica.bt import fit_strengths, performance_multiplier


def test_consistent_winner_ranks_highest() -> None:
    # A beats B and C every time; B beats C. Expect strength A > B > C, all finite.
    verdicts = [
        (1, 2, 1), (1, 2, 1), (1, 3, 1), (1, 3, 1), (2, 3, 2), (2, 3, 2),
    ]
    s = fit_strengths([1, 2, 3], verdicts)
    assert s[1] > s[2] > s[3]
    assert all(abs(v) < 100 for v in s.values())  # regularisation keeps it finite


def test_ties_keep_strengths_equal() -> None:
    s = fit_strengths([1, 2], [(1, 2, None), (1, 2, None), (1, 2, None)])
    assert abs(s[1] - s[2]) < 1e-6


def test_strengths_are_mean_zero_in_log_space() -> None:
    s = fit_strengths([1, 2, 3], [(1, 2, 1), (2, 3, 2)])
    assert abs(sum(s.values())) < 1e-6


def test_undefeated_with_thin_evidence_is_shrunk_not_infinite() -> None:
    # One single win shouldn't catapult the winner to a runaway strength — the prior shrinks it.
    thin = fit_strengths([1, 2], [(1, 2, 1)])
    strong = fit_strengths([1, 2], [(1, 2, 1)] * 50)
    assert thin[1] > thin[2]
    assert strong[1] > thin[1]  # more evidence → more confident separation


def test_order_independence() -> None:
    a = fit_strengths([1, 2, 3], [(1, 2, 1), (2, 3, 2), (1, 3, 1)])
    b = fit_strengths([1, 2, 3], [(1, 3, 1), (1, 2, 1), (2, 3, 2)])
    for key in a:
        assert abs(a[key] - b[key]) < 1e-9


def test_performance_multiplier_is_bounded_and_monotonic() -> None:
    assert performance_multiplier(0.0, 1.0, 0.7, 1.4) == 1.0
    assert performance_multiplier(5.0, 1.0, 0.7, 1.4) == 1.4  # clipped at the ceiling
    assert performance_multiplier(-5.0, 1.0, 0.7, 1.4) == 0.7  # clipped at the floor
    assert performance_multiplier(0.2, 1.0, 0.7, 1.4) > performance_multiplier(0.1, 1.0, 0.7, 1.4)
