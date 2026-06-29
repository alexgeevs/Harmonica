"""Bradley-Terry ranking for cover renditions (Phase D).

WHAT IT IS. When you only have *pairwise* judgements ("rendition A is better than B") and never an
absolute score, you can still recover a single number per item. The Bradley-Terry model says each
item ``i`` has a hidden positive *strength* ``pi_i`` and the chance it beats ``j`` is
``pi_i / (pi_i + pi_j)``. Fitting the strengths to all the verdicts gives a self-consistent ranking:
beating strong opponents counts for more than beating weak ones, and it works even when the
comparison graph is sparse or the judgements are mildly contradictory (A>B, B>C, C>A).

This module fits those strengths from the raw verdict log and returns them on a log scale with mean
0 (so ``> 0`` means "above the set average", ``< 0`` below). A small Gaussian prior (a phantom
average opponent) keeps an undefeated or winless rendition finite and shrinks a barely-compared set
toward "all equal", so two covers with one verdict don't swing wildly.

Ties ("about the same") are counted as half-credit to each side. The fit is order-independent: it
is always recomputed from the full set of verdicts, never updated online.
"""

from __future__ import annotations

import math

# A verdict is (track_a_id, track_b_id, winner_track_id | None-for-tie).
Verdict = tuple[int, int, int | None]


def fit_strengths(
    track_ids: list[int],
    verdicts: list[Verdict],
    prior_strength: float = 1.0,
    max_iter: int = 500,
    tol: float = 1e-10,
) -> dict[int, float]:
    """Return ``{track_id: bt_strength}`` (log scale, mean 0) for the renditions in one cover set.

    ``prior_strength`` is the weight of the phantom average opponent: higher = stronger shrinkage
    toward equal strengths when evidence is thin.
    """
    unique_ids = list(dict.fromkeys(track_ids))
    n = len(unique_ids)
    if n == 0:
        return {}
    if n == 1:
        return {unique_ids[0]: 0.0}

    index = {tid: k for k, tid in enumerate(unique_ids)}
    wins = [0.0] * n
    games = [[0.0] * n for _ in range(n)]
    for a, b, winner in verdicts:
        if a not in index or b not in index or a == b:
            continue
        ia, ib = index[a], index[b]
        games[ia][ib] += 1.0
        games[ib][ia] += 1.0
        if winner is None:
            wins[ia] += 0.5
            wins[ib] += 0.5
        elif winner == a:
            wins[ia] += 1.0
        elif winner == b:
            wins[ib] += 1.0
        else:
            # winner not in this pair — treat as a tie rather than dropping the evidence.
            wins[ia] += 0.5
            wins[ib] += 0.5

    # Zermelo / MM fixed-point iteration with a phantom strength-1 opponent for regularisation.
    pi = [1.0] * n
    half_prior = prior_strength * 0.5
    for _ in range(max_iter):
        updated = [0.0] * n
        for i in range(n):
            denom = half_prior / (pi[i] + 1.0) + half_prior / (pi[i] + 1.0)
            for j in range(n):
                if games[i][j] > 0.0:
                    denom += games[i][j] / (pi[i] + pi[j])
            numer = wins[i] + half_prior  # phantom contributes half_prior expected wins
            updated[i] = numer / denom if denom > 0.0 else pi[i]
        # Normalise to geometric mean 1 so the strengths are identifiable (mean-0 in log space).
        log_mean = sum(math.log(max(x, 1e-12)) for x in updated) / n
        scale = math.exp(log_mean)
        updated = [max(x / scale, 1e-12) for x in updated]
        delta = max(abs(updated[i] - pi[i]) for i in range(n))
        pi = updated
        if delta < tol:
            break

    return {unique_ids[k]: math.log(pi[k]) for k in range(n)}


def performance_multiplier(
    bt_strength: float,
    gamma: float,
    minimum: float,
    maximum: float,
) -> float:
    """Map a within-set BT log-strength to a bounded selection multiplier. ``exp(gamma·strength)``
    turns the relative log-strength into a ratio, clipped so a dominant rendition can't run away."""
    value = math.exp(gamma * bt_strength)
    return min(max(value, minimum), maximum)
