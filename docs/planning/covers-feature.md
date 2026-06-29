# Covers & rendition selection — feature reference

How Harmonica handles songs that exist in several **renditions** (covers, dubs, reprises, alternate
mixes). Shipped across Phases C–G (2026-06-29). The whole feature is **off by default** behind the
`cover_two_level_enabled` setting; with it off, the algorithm behaves exactly as before (a
golden-parity test guarantees byte-identical seeded queues on a no-`sub_group` library).

Renditions of one song share a `sub_group` (the "version family"). That field already existed for
cooldowns; covers build a second selection layer on top of it.

## What it does (when enabled)

1. **Two-level selection.** Each generation slot first picks a *song* (a unit = all renditions
   sharing a `sub_group`; a song with no covers is its own singleton unit), then picks *which
   rendition* to play.
2. **Logarithmic exposure.** A song with many covers appears only a little more often, never
   proportionally more. Unit weight includes `L(n) = 1 + log_base(n_covers)`; with the default base
   4, two covers → ×1.5, ten covers → ×2.66 (not ×10). The base is the **`cover_count_log_base`**
   setting. Because the within-unit term is a *v-weighted average* (not a sum), cover count enters
   selection **only** through `L(n)` — proven sublinear.
3. **Which rendition.** After a song is chosen, the rendition is picked by: its own playback context
   (cooldowns, history, etc.) × a within-set preference made of (a) **performance** — a learned
   Bradley-Terry strength from A/B verdicts, falling back to a directly-rated `performance` star,
   (b) each rendition's **own individual rating** (computed but never shown — the displayed rating is
   the shared song-level one), and (c) a small, fixed **original-rendition nudge**
   (`cover_original_bonus`, non-decaying).
4. **A/B comparison.** When you're "active" (you've rated ≥4 of the last 5 songs) and land on an
   eligible cover set, two renditions are spliced in to play back-to-back. During the second one a
   card asks "which is better?" (first / about the same / this) with a **replay-the-first** button.
   Your verdict feeds a Bradley-Terry ranking.

## Bradley-Terry (the performance ranking)

You only ever judge renditions *pairwise* ("A is better than B"), never on an absolute scale.
Bradley-Terry gives each rendition a hidden strength `π`, with `P(A beats B) = π_A / (π_A + π_B)`;
fitting it to all verdicts yields a self-consistent ranking where beating a strong rendition counts
for more. We store strengths on a log scale, mean 0 (positive = above the set average). A phantom
"average opponent" prior keeps thin/undefeated evidence finite; ties are half-credit. The fit is
**recomputed from the full raw verdict log** every time (order-independent, self-healing) — see
`bt.py` and `cover_ranking.py`. Choosing Bradley-Terry was Claude's call (see the attribution ledger
in `session-log.md`).

## Lifecycle

A set's `comparison_phase` moves `stars` → `bootstrapping` (once it has verdicts) → `settled`
(every rendition has ≥ `cover_comparison_min_per_cover` comparisons and the ranking is well
separated, or a hard ceiling of `cover_comparison_max_total` verdicts is hit). A settled set stops
prompting; the track editor shows its status and a **Compare again** button (`POST
/cover-sets/{sub_group}/reopen`) to reopen it.

## Data model (all additive tables — `create_all`, no migration)

- `cover_comparisons` — append-only raw A/B verdict log (the source of truth).
- `cover_rendition_state` — cached BT strength + comparison count per rendition (rebuilt from the log).
- `cover_set_state` — per-set lifecycle phase + total verdicts.
- `tracks.is_original_rendition` — additive column marking the original within a set.

## API

- `POST /cover-verdicts` — record an A/B verdict; validates the pair, refits BT, updates caches.
- `GET /cover-sets/{sub_group}` — current phase + per-rendition relative strengths.
- `POST /cover-sets/{sub_group}/reopen` — reopen a settled set.
- `GET /cover-comparisons/next?sub_group=…` — the next A/B pair as two ready-to-queue items, or
  `null` when ineligible/settled.

## Export / import (Phase F)

`GET/POST /library/*-json` carry the raw history — `rating_samples`, `cover_comparisons`, and
`is_original_rendition` — keyed by `song_id`/`factor_key` so they survive a move to another device
(local row ids differ). Device-local `session_id`/`run_id` are stripped. On import the BT caches are
**recomputed from the imported verdicts**, never trusted from the file. Re-importing the same export
is idempotent.

## Settings (all in the "Covers (experimental)" section unless noted)

| Key | Meaning |
| --- | --- |
| `cover_two_level_enabled` | Master switch (default **off**). |
| `cover_count_log_base` | Log base for the cover-count exposure boost (default 4). |
| `cover_original_bonus` | Fixed within-set nudge for the original rendition (default 0.1). |
| `cover_comparison_enabled` | Allow the A/B prompt (default on; config-only). |
| `cover_perf_*`, `cover_bt_prior_strength` | BT multiplier bounds / regularisation (config-only). |
| `cover_comparison_min_covers` / `_cooldown_songs` / `_min_per_cover` / `_max_total` / `_settle_gap` | Eligibility + settling (config-only). |
| `cover_active_window` / `cover_active_min_rated` | "Active listener" detection (config-only). |

## How to try it

1. Turn on **Two-level cover selection** in Settings → Covers.
2. Have a `sub_group` with ≥4 renditions that have media (the real ~250-song batch with its
   dubs/covers is the natural test bed; mark one as the original in the track editor).
3. Generate a queue and rate a few songs; when "active", an A/B pair will be queued and the
   comparison card will appear on the second rendition.

## Tests

`test_covers.py` (parity + logarithmic exposure + per-cover rating + original nudge), `test_bt.py`
(BT properties), `test_cover_ranking.py` (pair selection / settle), `test_serialization_covers.py`
(export-import round-trip + idempotency), and the `cover_*` cases in `test_api.py`.
