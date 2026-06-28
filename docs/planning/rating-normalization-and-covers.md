# Rating Normalisation & Cover Comparison

Direction set by the user on 2026-06-27. Two related goals: make the rating signal **trustworthy**
(strip out mood noise) and make it **expressive enough for near-duplicates** (many covers of one
song). This is a plan; pieces are marked as they land.

## Today's data model (for reference)

- Ratings overwrite: one `TrackRating` row per `(track, factor)` with a single `value`. There is **no
  history**, so mean/SD cannot be computed yet.
- Default rating factors: `lyrics`, `music`, `inspiration`, `focus`, `overall`. A factor already has
  `applies_to_lyrics`, `applies_to_instrumental`, and `applies_to_variants_only` flags.
- Covers/variants = tracks sharing a `sub_group` (the version family). The algorithm counts variants,
  cools down `sub_group` so covers don't play back-to-back, and `applies_to_variants_only` factors
  only count when a song has >1 variant.
- `effective_rating` (weighted factor average) → `rating_multiplier` per track → used in scoring.

## Feature 1 — Rating normalisation (mood / outlier regression)

**Problem.** A single overwrite rating is mood-sensitive. The user wants repeated ratings over time,
with outliers regressed toward the mean ("the user's mood was different").

**Key clarification (user, 2026-06-27):** the standard deviation is derived **library-wide**, once the
*majority* of songs have been rated (hopefully most more than once) — not per-song (too few samples per
song for a reliable per-song SD). So the SD is a global yardstick for "how much rating variation is
normal," and a song's individual rating is judged an outlier relative to **that song's own mean** using
the global SD as the scale.

**Design.**
1. **Rating history (additive).** New `rating_samples(id, track_id, factor_id, value, run_id?,
   created_at)` — one row per rating action. `TrackRating.value` stays as the cached *effective*
   estimate (so the algorithm/UI are unchanged); it is recomputed from the samples.
2. **Library SD readiness.** Compute per-factor mean `μ_f` and SD `σ_f` across *all* samples, but only
   once coverage is sufficient (e.g. ≥ ~60% of rateable songs have ≥1 sample). Until then,
   normalisation is inert and the latest rating is used as-is.
3. **Outlier regression (winsorising).** For a song+factor with several samples, compute the song mean
   `μ_s`. Any sample with `|x − μ_s| > k·σ_f` is pulled in to `μ_s ± k·σ_f` (winsorised), then the
   effective value = mean of the winsorised samples. `k` defaults to ~1.0 (user said "a standard
   deviation"); tunable. With only one sample, fall back to it directly.
4. **Session-mood correction (the ">10 songs" part).** Within a listening session (a `PlaylistRun`)
   with >10 rated songs, estimate the session bias `b = mean(sample − μ_s)` over that session's rated
   songs. If `|b|` is large, subtract `b` from that session's samples before aggregating — i.e. correct
   a uniformly generous/grumpy session. Off until the library SD is ready.

**Settings (all tunable, real controls):** `rating_normalization_enabled` (default on),
`rating_outlier_sd` (k, default 1.0), `rating_session_mood_correction` (default on),
`rating_session_min_songs` (default 10), `rating_coverage_ready_fraction` (default 0.6).

## Feature 2 — Cover comparison ("which rendition is better")

**Problem.** Some songs have many covers (up to ~10). Rating each 0–5 in isolation is a poor way to say
which rendition you prefer. Better: pairwise A/B — play two, synced, pick the better one.

**Scope & lifecycle.**
- Eligible when a cover set (same `sub_group`) has **≥ 4** covers. Below that, no comparison UI, but the
  algorithm still rotates renditions (existing sub_group cooldown + weighted choice).
- Comparison is **only offered while the UI is actively in use** (`ui_active`), i.e. during the setup
  phase. Background/auto queues never trigger it.
- It's a **bootstrapping phase**: once enough input exists for a set (every cover in ≥ N comparisons and
  the order is stable), stop comparing and **return to the star system** for that set.
- Pick two covers at a time (not all 10); don't always pick the same two — prioritise pairs that most
  reduce ranking uncertainty (adjacent in current order / fewest comparisons).

**Ranking.** Pairwise wins → an **Elo / Bradley–Terry** score per cover *within its set*. This produces a
relative order of renditions, not an absolute like-score.

**Open questions (being confirmed with the user):**
- *Sync semantics* — how to align two covers of different length/tempo during A/B.
- *Shared vs cover-specific factors* — which judgments carry across all covers of a song vs belong to a
  single rendition. Proposed default: shared = {lyrics, inspiration}; cover-specific = {music, focus,
  overall}. Implemented as a per-factor `shared_across_covers` flag (editable in the UI).
- *What the verdict drives* — proposed: the pairwise order decides **which rendition plays** when the
  algorithm picks that song; the song's cross-song frequency still comes from the shared factors + the
  set's representative rating. (i.e. "better" = better rendition, not "I like this song more.")

## Corrections & clarifications (2026-06-27, after Feature 1 shipped)

These refine/override the blueprint where they differ:

- **Displayed rating = plain AVERAGE of the user's past ratings** (fractional), NOT the raw latest
  star. This supersedes the blueprint's "TrackRating.value stays the raw latest star for display."
  Implemented: `plain_rating_averages()` feeds `TrackRead.ratings`; the UI shows fractional stars +
  the numeric average; each star tap records ONE new sample (only the tapped factor is sent, so the
  average is never re-recorded as a fake rating); the bulk track-save no longer touches ratings.
- **Outliers are judged against that plain average** (`mu_c` = the series mean) — already how
  winsorising works. The internal normalised ("magic") value is separate and only the algorithm sees
  it (`ratings_effective`).
- **Multiplier scaling is already continuous** and needs no change: rating 4 → 1.6×, only a maximal 5
  → the max (2×), floor 0.5× at 0; `song_rating_min_multiplier` / `song_rating_max_multiplier` are
  already real settings controls. (The earlier "2×" example just used max ratings.)
- **Weak cross-song type link** (user seed idea): a good rating nudges a type up while same-type songs
  are still spaced apart — much of this already exists (group rating-multipliers + group cooldown +
  fractional multi-type membership). To be verified and made tunable; see the algorithm-roadmap doc
  (from the brainstorm review) for the refined form.

## Architecture decisions — verbatim Q&A (2026-06-27)

The user asked these be recorded as evidence of intent. Captured verbatim.

**Clarification on the SD (unprompted):** "The standard deviation would be derived once the majority of
songs have already been rated, hopefully most more than once."

**Q: How should two covers be 'synced' during A/B?**
> "Probably this [same-time + nudge], but that's true, I just came across a cover which is labelled as
> 'extended'. Another one I found does in fact have a wholely different tempo due to being quite
> modified. Let's actually change this to have a preference to have two covers play **consecutively**
> (when the UI is on, classed as when out of the last 5 songs 4 received a rating, not necessarily the
> screen is definitely on all the time), and then during the second one **ask which is better**, with an
> option to **go back to the last one for a few moments at around the same % through** to compare."

**Q: Which factors are shared across covers vs cover-specific?** (selected lyrics, inspiration, music, focus)
> "Well, I'm thinking that the ratings a user sees can probably be shared (**except for performance**), as
> in the stars in the sidebar (or wherever the ratings are), while otherwise **internally within each song
> the cover-specific ratings are also saved**. This goes along with the fact that our algorithm choses a
> song based off of the ratings for it (you missed **overall** in the above list by the way, and that can
> also be affected by the other ratings, so **half of what constitutes overall is user feedback, and half
> is the other factors' user feedback**), and then once a song is chosen, a cover can be chosen based off
> of cover-specific ratings (note that the **original can have a slightly higher rating, but not by
> much**). Also, note that the ratings of songs increase in a **logarithmic scale**, so a song with 10
> covers will barely have a higher chance of appearing than a song with 9 covers, while one with 2 covers
> doesn't lead to it appearing twice as much as a song without a cover (the **base of the log** can be
> another factor that makes up the algorithm and can be customised in settings, if not already). I hope my
> input isn't too disorganised, write this back-and-forth down in an md file for evidence of my
> architecture decisions in future. Do your best to proceed."

**Q: What should the 'which is better' verdict drive?** (chose "also boost the song")
> "2, as the song's general rating comes from the covers (as per the above description), and then only
> once a song is selected is the cover chosen (this also helps with avoiding cover-by-cover repetition)."

### Consequences of the above (supersedes the "Open questions" framing earlier)

- **Two-level selection.** Pick a **song** (cover set) using its song-level (shared) ratings, then pick a
  **cover** within it using cover-specific ratings. Avoids cover-by-cover repetition by construction.
- **Cover count → logarithmic appearance.** A song's selection weight scales like `1 + log_base(n_covers)`,
  base tunable in settings — NOT linearly in the number of covers (today each cover is an independent
  candidate, which is ~linear; this must change).
- **`performance`** becomes a new **cover-specific** factor (the A/B verdict feeds it). The other factors
  (lyrics, music, inspiration, focus, overall) are **shown shared** at song level; cover-specific values
  may still be stored internally.
- **`overall` = 50% direct user rating + 50% mean of the other factors.**
- **Original-rendition prior:** the original cover gets a small positive bias in cover selection.
- **Comparison flow = consecutive playback**, not simultaneous sync: play cover A, then cover B; during B
  ask "which was better?", with a "replay A briefly at ~same %" affordance.
- **"Active" trigger:** comparisons fire only when engaged — defined as **≥4 of the last 5 songs rated**.
- Eligible for sets with **≥4 covers**; bootstrap then **revert to stars** once enough input.

## Rollout

- **Phase A.** Rating history table + library-SD readiness + winsorising effective estimate + settings.
- **Phase B.** Session-mood correction.
- **Phase C.** Two-level selection + log cover-count scaling + `performance` factor + original prior.
- **Phase D.** Cover-comparison data model (comparisons table) + performance derivation from A/B verdicts.
- **Phase E.** Comparison UX: consecutive playback, "which was better", brief replay, "active" detection,
  pair selection, phase-out back to stars.

*(A multi-agent design review refined the detailed math/schema below — see the next section, appended
after the review.)*


---

# Finalised blueprint (multi-agent design review, 2026-06-27)

_Synthesised from a 22-agent map→design→adversarial-critique→synthesis workflow. This is the implementation contract; it supersedes the rougher sketches above where they differ._


## Overview

Two additive features built on raw-history + lazy-normalisation + two-level cover selection, with zero destructive migration. RATING NORMALISATION (Feature 1): every rating action appends a raw row to a new append-only `rating_samples` table; `TrackRating.value` is left UNCHANGED (still the latest raw star), so display, the rated-badge, export and all current consumers keep working untouched. The algorithm's per-song rating is recomputed LAZILY inside `playlist.load_algorithm_inputs` each generation from the samples, because the library-wide SD shifts on every write and any persisted per-track normalised cache would go globally stale. The per-(cover,factor) effective value is: session-mood-correct -> winsorise (user-verbatim) -> empirical-Bayes shrink toward the factor grand mean (this realises the user's 'regress outliers toward the mean' and fixes winsorise's n<=2 inertness that all four statistical reviewers flagged). The SD yardstick is the POOLED WITHIN-SERIES SD (the correct scale for 'deviation from a song's own mean', which is exactly the user's described global yardstick). `overall` becomes 0.5*direct + 0.5*mean(other shared factors) and is the SOLE song-level rating input (excluded from any further averaging) so there is no double-count; the same normalised per-unit overall drives BOTH the song multiplier and the group multiplier (unifying two paths that diverge today). COVERS (Feature 2): each `sub_group` collapses to one SONG candidate per slot inside `generate_playlist` (one `AlgorithmTrack` per cover is still kept, so flat cold-start indices and the NOT-NULL `PlaylistItem.track_id` survive); the unit weight makes cover-count dependence EXACTLY `1+log_base(n_covers)` because the within-set aggregate is an AVERAGE not a sum, so 10 covers barely beats 9 and 2 covers is far from 2x, and performance is frequency-neutral by construction. Within the chosen unit a concrete cover is picked from a regularised Bradley-Terry 'performance' strength (relative, never written as an absolute star) plus a small decaying original prior. Cover A/B comparison is an explicit foreground-only, throttled override (visibility + active>=4/5-rated + eligible>=4-covers + throttle), never an emergent product of the algorithm, so background listening never gets two covers back-to-back; consecutive playback reuses the single <video> element (preserving the loudness meter), and sets revert to stars once settled or a hard comparison ceiling is hit. Additive-column helpers are moved into `init_db()` so cli/seed paths stop silently missing new columns; the only new column is `tracks.is_original_rendition`, everything else is four new tables that `create_all` makes for free.

## Locked decisions

- Rating history lives in a NEW append-only rating_samples table; TrackRating.value stays the RAW latest star (no semantic change). Rationale: avoids the 'user's tapped star visibly shifts to a fractional normalised value' blocker and the 'export injects normalised numbers as raw' blocker.
- Normalisation is computed LAZILY in load_algorithm_inputs from samples each generation; per-factor SD cached in AppSetting('rating_factor_stats'). Rationale: the library SD changes on every write, so a persisted per-track normalised cache would go globally stale for every other track.
- SD yardstick = POOLED WITHIN-SERIES SD (within each (cover,factor) rating series), not the total/between-song SD. Rationale: it is the only correct scale for |x - mu_s| mood deviation and is literally the user's 'global yardstick for deviation from a song's own mean'; total SD is dominated by real quality differences and makes winsorising inert (4 reviewers).
- Effective value = winsorise (user-verbatim) THEN empirical-Bayes shrink toward the factor grand mean mu_f. Rationale: winsorising honours the user's exact words; shrinkage realises the user's repeated 'regress toward the mean' phrasing AND fixes winsorise being a no-op at n<=2, the headline statistical blocker.
- Readiness keeps the user's >=60% coverage gate but ADDS a depth guard (>=20 multi-rated songs and >=30 samples/factor) and a smooth ramp; pre-readiness uses the plain per-song mean (not 'latest'). Rationale: depth+ramp remove the 'ready-but-inert' and 'library-wide discontinuous jump' problems without contradicting the user.
- Session-mood = leave-session-out residuals on qualifying songs only, reliability-shrunk and thresholded; bias=0 if too few qualifying songs. Rationale: removes the self-cancellation circularity and the cold-start confound (it correctly goes inert during all-first-rating sessions).
- overall = 0.5*direct + 0.5*mean(other shared factors) and is the SOLE song-level rating; it is NOT also re-averaged with those factors. Rationale: eliminates the double-count every reviewer flagged while matching 'the algorithm chooses based on overall, half direct half others'.
- Song multiplier AND group multiplier consume the SAME normalised per-UNIT overall (one value per cover set). Rationale: removes the song-vs-group rating divergence and prevents N covers contributing N times to group weighting (linear inflation).
- Two-level selection via in-slot grouping; one AlgorithmTrack per cover is kept. Rationale: gives EXACT logarithmic exposure and exactly-one-cover-per-slot while preserving flat cold-start indices, the compressed soft-bias, the 3-tier fallback, and the NOT-NULL PlaylistItem.track_id.
- Unit weight is built so cover-count dependence is exactly L(n)=1+log_base(n) (the within-set term is a v-weighted AVERAGE, not a sum); performance affects only WHICH cover, never how often the song plays. Rationale: provably logarithmic and matches the user's two-level intent verbatim.
- cover_log_base default = 4.0 (not 2.0). Rationale: B=2 makes 2 covers exactly 2x (violates 'not twice as likely'); B=4 gives 2->1.5x, 9->2.58x, 10->2.66x ('barely' above 9).
- Cold-start coverage is redefined at the SONG/UNIT level; the played-twice threshold counts UNITS not covers. Rationale: matches 'every song played once before half the library twice' (covers ARE the same song) and avoids forcing ~N plays per cover set during cold start.
- Singleton (no-sub_group) units keep the LONG song-cooldown horizon (~total tracks); only real cover sets get the 30-slot unit cooldown. Rationale: preserves the song-level anti-repeat guarantee for the ~99% non-cover library that would otherwise shrink to a 30-slot memory.
- Cover ranking = regularised Bradley-Terry MAP (phantom-average-player Gaussian prior + Davidson tie term), refit from raw verdicts. Rationale: order-independent and finite under separation/disconnection; online Elo is unstable at the ~3-10 verdicts/set regime.
- Performance is RELATIVE within-set, stored only in cover_rendition_state.bt_strength; never written as a rating_sample or an absolute 0..5 star. Rationale: keeps it out of all SD/readiness/overall/'rated' statistics (it is a deterministic function of verdicts, not an exchangeable observation) and stops adding/removing a cover from rewriting absolute stars.
- Original prior = small DECAYING selection multiplier 1 + delta*n0/(n0 + comparisons_in_set), delta=0.05. Rationale: 'slightly higher but not by much' AND it washes out as A/B evidence accumulates instead of a permanent 15% boost on a proven-worse original.
- A/B is an explicit, FOREGROUND-only, throttled override (visibility AND active>=4/5-rated AND eligible>=4-covers AND throttle), spliced client-side; an unanswered pair aborts and never repeats. Rationale: prevents the background back-to-back-cover repetition the whole product exists to avoid.
- Revert-to-stars terminates on (every cover >= min_per_cover comparisons AND BT order stable beyond standard error) OR a hard cover_comparison_max_total ceiling. Rationale: guarantees the lifecycle ends even for near-equal/intransitive covers.
- Rating writes carry an optional client rating_session_id (one 'sitting', covering BOTH curation and playback ratings); rating_samples.session_id keys session-mood. Rationale: PATCH /tracks has no run context today and MOST ratings happen during curation, outside any PlaylistRun.
- All ensure_additive_* helpers move INTO init_db() (db.py); the only new column is tracks.is_original_rendition. Rationale: cli.py and seed_demo_library.py call init_db() but NOT the helpers today, so any new column would be missing there.
- Finite-guard (NaN/inf -> 0) before every weighted_choice and guard every mean-of-empty. Rationale: a single NaN makes the current weighted_choice silently always-pick-the-last item.
- ~12 curated real controls in two new Settings sections; deep estimator constants stay internal config.Settings fields with no SettingDefinition. Rationale: keeps the user-named knobs real and explained without a wall of inscrutable statistical sliders.

## Schema additions (all additive)

- NEW TABLE rating_samples (model RatingSample; auto-created by create_all, just import it): id INTEGER PK; track_id INTEGER FK->tracks.id NOT NULL index ondelete CASCADE; factor_id INTEGER FK->rating_factors.id NOT NULL index; value FLOAT NULLABLE (raw 0..5 clamped at write; NULL = explicit clear/retract marker); source VARCHAR(16) NOT NULL default 'user' ('user'|'import'); session_id VARCHAR(64) NULLABLE index (client 'sitting' id for session-mood); run_id INTEGER FK->playlist_runs.id NULLABLE; created_at DATETIME NOT NULL default now_utc index. Composite index (factor_id, track_id, created_at). NO unique constraint (history accumulates).
- NEW TABLE cover_comparisons (model CoverComparison): id PK; sub_group VARCHAR(255) NOT NULL index; track_a_id INTEGER FK->tracks.id NOT NULL; track_b_id INTEGER FK->tracks.id NOT NULL; winner_track_id INTEGER FK->tracks.id NULLABLE (NULL = 'about the same' tie); pct_a FLOAT NULLABLE; pct_b FLOAT NULLABLE (playback %-through at verdict, for the replay-A affordance); session_id VARCHAR(64) NULLABLE; run_id INTEGER FK NULLABLE; created_at DATETIME index. Append-only raw verdict log; BT is recomputed from it (never stored as an online running value).
- NEW TABLE cover_rendition_state (model CoverRenditionState): id PK; track_id INTEGER FK->tracks.id UNIQUE index; sub_group VARCHAR(255) index; bt_strength FLOAT NOT NULL default 0.0 (within-set Bradley-Terry log-strength, mean ~0); comparison_count INTEGER NOT NULL default 0; updated_at DATETIME. Cache so cover-pick and pair-selection don't refit per slot.
- NEW TABLE cover_set_state (model CoverSetState): sub_group VARCHAR(255) PRIMARY KEY; comparison_phase VARCHAR(16) NOT NULL default 'stars' ('stars'|'bootstrapping'|'settled'); total_comparisons INTEGER NOT NULL default 0; updated_at DATETIME. Per-set lifecycle flag for revert-to-stars / compare-again.
- ADDITIVE COLUMN tracks.is_original_rendition BOOLEAN NOT NULL default 0 — add to the EXISTING ensure_additive_track_columns additions dict (models.py:292-296). Marks the original within a sub_group for the cover prior. Expose in TrackRead/TrackUpdate (schemas.py:45,69) + track_to_schema/apply_track_update + serialization.track_to_payload.
- WIRING FIX: move ensure_additive_playlist_run_columns / ensure_additive_track_columns / ensure_additive_playback_event_columns calls INTO init_db() (db.py:25-28) right after create_all, and import the 4 new models there so they register on Base.metadata. Remove the now-redundant calls in api.create_app (or keep them idempotent). This guarantees cli.py and seed_demo_library.py (which only call init_db()) get the column.
- ONE-TIME idempotent backfill in init_db() (or a startup hook): for every TrackRating with value not NULL and zero rating_samples rows, insert one RatingSample(value=value, source='import', created_at=track.updated_at). Makes the live ~250-song DB history-capable; each backfilled song is n=1, so within-series SD is uninformative and normalisation correctly stays inert until re-rating.
- AppSetting JSON cache key 'rating_factor_stats' = {factor_key: {mu_f, sigma_f, n_samples, n_multi_rated_songs, coverage_fraction, ready: bool, alpha: 0..1}} — generic KV, no schema change; recomputed each generation in load_algorithm_inputs (live recompute is also acceptable, it is O(samples)).
- SERIALIZATION (serialization.py): export/import rating_samples (raw history, STRIP session_id/run_id as device-local), cover_comparisons, cover_rendition_state, cover_set_state, and tracks.is_original_rendition; on import RECOMPUTE caches (never trust exported normalised values). track_to_payload also adds is_original_rendition.
- schemas.py: TrackRead gains optional ratings_effective: dict[str,float|None] (the normalised value, for a subtle secondary display) and is_original_rendition: bool; TrackUpdate gains is_original_rendition and an optional rating_session_id; SettingsRead gains every new control field (or response validation fails).

## Scoring pipeline

- 1. load_algorithm_inputs loads Tracks (device-filtered FIRST), their rating_samples, cover_comparisons, cover_rendition_state, cover_set_state. variant_counts / n_covers are computed AFTER the included_track_ids filter, keyed by unit_key = track.sub_group if track.sub_group else f'__solo_{track.id}' (fixes the device-scope bug AND the sub_group=None giant-set bug).
- 2. Per-factor library stats: mu_f = mean of all (non-retract) samples of f; sigma_f = pooled within-series SD = sqrt( sum_series sum_i (x_i - mu_series)^2 / sum_series (n_series-1) ) over (cover,factor) series with n_series>=2; coverage_f = |rateable songs of f with >=1 sample| / |rateable songs of f|; ready_f = normalization_enabled AND coverage_f>=rating_coverage_ready_fraction AND n_multi_rated>=rating_min_multi_rated_songs AND n_samples>=rating_min_samples_for_sd AND sigma_f>1e-6; alpha_f ramps 0->1 across [ready_threshold, ready_threshold+0.2] coverage. Cached to AppSetting.
- 3. Per (cover c, factor f) effective value (normalization_algorithm): retract-trim -> session-mood subtract -> winsorise to mu_c +/- k*sigma_f (k=rating_outlier_sd) -> shrink toward mu_f with B=n/(n+lambda) -> ramp blend with plain mean. Empty/retracted series -> None.
- 4. Per UNIT u: for each shared factor f (all except 'performance'), shared_value(u,f) = mean over covers c in u of cover_effective(c,f) [None covers skipped]; direct_overall(u) = mean over covers of cover_effective(c,'overall'); overall_song(u) = 0.5*direct_overall + 0.5*mean(shared_value(u,f) for applicable f != overall), with the documented fallbacks. SongRatingMult(u) = rating_to_song_multiplier(overall_song(u), settings) [None -> 1.0 neutral preserved].
- 5. Group rating multipliers: aggregate_group_rating_multipliers is refactored to take the precomputed per-UNIT overall_song and contribute it ONCE per unit (share-weighted over the unit's combined memberships), so song and group ratings agree and covers don't inflate linearly. Folded into AlgorithmGroup.multiplier exactly as today (playlist.py:63-76).
- 6. Build AlgorithmTrack per cover with existing fields plus frozen: unit_key, n_covers (scoped), song_rating_multiplier=SongRatingMult(unit), perf_mult (precomputed from bt_strength or manual performance star, clipped to [cover_perf_min,cover_perf_max]), is_original_rendition, original_prior_mult. AlgorithmTrack.rating_multiplier is set to SongRatingMult(unit) so the disabled/singleton path matches today.
- 7. generate_playlist runs the two-level loop (cover_selection_algorithm). Per slot it still calls score_track per cover (UNCHANGED) and reads the explanation COMPONENTS to form A_c = base_score * manual_multiplier * history_multiplier * cold_start_multiplier * visual_multiplier * song_cooldown (deliberately EXCLUDING rating_multiplier and sub_group_cooldown to avoid double-counting; those become unit-level).
- 8. Unit weight W(u) = L(n_u) * SongRatingMult(u) * UnitCooldown(u) * Abar(u) where L(n_u)=1+log(n_u)/log(base) (base=cover_log_base, guarded base>1 & n>=1), UnitCooldown(u)=linear_recovery on sub_group_last_played for real sets / 1.0 for singletons, Abar(u)=sum_c(A_c*v_c)/sum_c(v_c), v_c=perf_mult(c)*original_prior_mult(c). Finite-guard each W; pick a unit via weighted_choice (uniform fallback on sum<=0).
- 9. Within the chosen unit pick a concrete cover by weight A_c*v_c (finite-guarded, uniform fallback); during unit-level cold-start first_coverage restrict to that unit's uncovered covers. Resolve to a real Track.id -> PlaylistItem.track_id. Three-tier zero-score fallback ladder is re-implemented at UNIT level (relax UnitCooldown, then group cooldowns, then song cooldown).
- 10. State update after pick: track_last_played[cover]=pos, track_repeat_count[cover]+=1, sub_group_last_played[unit]=pos (UnitCooldown), group_last_played for the cover's groups. Cold-start bookkeeping (cold_start_candidate_indices / cold_start_is_active) operates on UNITS: a unit is first_coverage if it has >=1 uncovered+unrated cover; played-twice threshold = len(units)/2.
- 11. Explanation gains cover_log_factor (=L(n)), n_covers, song_rating, cover_performance, original_prior so format.ts can surface 'one of N versions (log-weighted)' and 'this rendition chosen for performance/originality'.

## Normalisation algorithm (Feature 1)

- SERIES DEFINITION: the repeated-rating unit is a (cover Track, factor) pair. samples(c,f) = rating_samples rows for (c,f) with created_at after the most recent retract (value IS NULL) row; values are 0..5. If the latest row is a retract or there are no value rows, (c,f) is UNRATED -> effective None -> rating_to_song_multiplier(None)=1.0 (neutral path preserved for unrated/cleared).
- LIBRARY STATS (per factor f, once per generation, cached): mu_f = mean of all value samples of f. sigma_f = POOLED WITHIN-SERIES SD = sqrt( sum over series with n>=2 of sum_i (x_i - mu_series)^2  /  sum over those series of (n_series - 1) ). This is library-wide and per-factor (the user's yardstick) but measures only within-song mood bounce, not between-song quality. NOTE/DEVIATION (flagged to user): 'SD across all samples' is read as within-series pooled SD, the only scale meaningful for |x-mu_s|; raw total SD would make k=1 winsorising inert.
- READINESS GATE: ready_f = rating_normalization_enabled AND coverage_f >= rating_coverage_ready_fraction (0.6, user) AND n_multi_rated_songs(f) >= rating_min_multi_rated_songs (20) AND n_samples(f) >= rating_min_samples_for_sd (30) AND sigma_f > 1e-6. coverage denominator guarded (0 rateable -> ready False). When NOT ready: effective(c,f) = plain mean of the series (always-on mood averaging; strictly better than 'latest'); winsorise/shrink/session-mood are skipped.
- SESSION-MOOD (Phase B; only when ready_f AND rating_session_mood_correction). A session = samples sharing session_id (fallback: same created_at calendar day). Qualifying songs in session R = covers with >=1 sample of f OUTSIDE R. If R has > rating_session_min_songs (10) DISTINCT rated songs AND >= a minimum count of qualifying songs: b = mean over qualifying in-session samples of (x - mu_c^{excl R}) [leave-session-out, NOT falling back to mu_f]. Reliability shrink b_hat = b * m_q/(m_q + rating_session_bias_pseudocount=10). Apply x' = clip(x - b_hat, 0, 5) ONLY if |b_hat| > rating_session_bias_min_sd*sigma_f (0.5). Otherwise b_hat=0. mean-of-empty -> 0. (Inert during all-first-rating cold-start sessions by construction.)
- WINSORISE (user-verbatim; only when ready_f): given mood-corrected samples X' (len n). If n==1: w = X'[0]. Else mu_c = mean(X'); bound = rating_outlier_sd (k, default 1.0) * sigma_f; X'' = [clip(x, mu_c-bound, mu_c+bound) for x in X']; w = mean(X''). Winsorising pulls a one-sided mood spike back to mu_c +/- k*sigma_f.
- SHRINK toward grand mean (empirical Bayes; only when ready_f, realises the user's 'regress outliers toward the mean'): eff_norm = mu_f + B*(w - mu_f), B = n / (n + rating_shrinkage_pseudocount). Default pseudocount 1.0 -> n=1 gives B=0.5 (a lone rating is pulled halfway to the library norm = exactly 'their mood was different'), n=5 gives B=0.83 (trusted). This is what makes Feature 1 do real work at the common n=1..2 (winsorise alone is a no-op there).
- RAMP (no library-wide cliff): effective(c,f) = (1 - alpha_f)*plain_mean + alpha_f*eff_norm, alpha_f rising smoothly 0->1 across the coverage band just past the readiness threshold. So crossing 60% does not snap every song at once.
- OVERALL = 50/50 (no double-count): overall is NOT a member of any averaged factor set. For unit u: others = applicable shared factors {lyrics, music, inspiration, focus} (gated by has_lyrics / instrumental). overall_song(u) = 0.5*direct_overall(u) + 0.5*mean(shared_value(u,f) for f in others). If only direct present -> direct_overall; if only others -> mean(others); if neither -> None. 'performance' is NEVER in others (user: 'except performance'). This single overall_song is THE song-level rating used for both song and group multipliers; sub-factors enter exactly once (via the 0.5*mean term).
- CROSS-COVER AGGREGATION: shared_value(u,f) = mean over covers of each cover's EFFECTIVE value (each already shrunk by its own n), NOT a pool of raw samples — so a heavily-rated rendition cannot swamp the song-level estimate. direct_overall(u) = mean over covers of cover overall-effective.
- WRITE PATH (api.upsert_ratings): for each {factor_key: value} append a RatingSample(value clamped 0..5 or NULL for clear, session_id from payload, run_id if known, source='user'); STILL upsert TrackRating.value = the raw value (unchanged) so display/badge/export are stable. No per-track normalised value is persisted; normalisation is recomputed at generation time. effective_rating (ratings.py:61) is retained for back-compat but the algorithm's song rating now comes from the new normalisation path.
- PERFORMANCE EXCLUSION: 'performance' is cover-specific and never enters mu_f/sigma_f/coverage/overall/'rated' (it lives in cover_rendition_state, derived from verdicts). So BT refit jitter cannot pollute the rating statistics and A/B engagement does not inflate the rated-coverage stat.

## Cover selection algorithm (Feature 2)

- UNITS: group AlgorithmTracks by unit_key = sub_group or f'__solo_{id}' so every no-cover song is its OWN singleton (never one giant None-set). n_u = number of covers in the unit within the device-scoped pool (computed once per generation).
- LOG WEIGHT: L(n) = 1 + log(n)/log(base), base = cover_log_base (default 4.0; clamped >1 at read so a bad persisted snapshot can't divide by zero). L(1)=1 (singletons unaffected = backward compatible), L(2)=1.5, L(9)=2.58, L(10)=2.66. Applied ONCE per unit.
- PER-COVER CONTEXT: from each cover's score_track explanation, A_c = base_score * manual_multiplier * history_multiplier * cold_start_multiplier * visual_multiplier * song_cooldown. It deliberately EXCLUDES rating_multiplier (song-level now) and sub_group_cooldown (unit-level now) so nothing is double-counted. A_c keeps each cover's group cooldown (inside base_score) and exact-rendition song_cooldown.
- WITHIN-SET PREFERENCE: v_c = perf_mult(c) * original_prior_mult(c). perf_mult(c) = clip(exp(gamma*bt_strength_c), cover_perf_min_multiplier=0.7, cover_perf_max_multiplier=1.4) when comparison_count>0, else rating_to_song_multiplier(manual performance star) if the user rated performance directly, else 1.0. original_prior_mult(c) = 1 + cover_original_prior * n0/(n0 + total_comparisons_in_set) if is_original_rendition else 1.0 (decays toward 1).
- UNIT SELECTION WEIGHT: W(u) = L(n_u) * SongRatingMult(u) * UnitCooldown(u) * Abar(u), where Abar(u) = sum_c(A_c * v_c) / sum_c(v_c) is the v-weighted AVERAGE of the per-cover context. UnitCooldown(u) = linear_recovery(distance since the set last played, sub_horizon=min(30,total), sub_group_cooldown_floor) for real cover sets; = 1.0 for singletons (whose anti-repeat is the long-horizon song_cooldown already inside A_c).
- PROOF OF LOGARITHMIC EXPOSURE: marginal P(select unit u) = W(u)/sum_u' W(u'). Abar is an AVERAGE so it does NOT grow with n_u, and SongRatingMult/UnitCooldown are n-independent; the ONLY n-dependence is the explicit L(n_u). Hence a set's total selection mass scales exactly as 1+log_base(n) — 10 covers ~2.66x a no-cover song (not 10x), 10 barely above 9, 2 covers 1.5x (not 2x). This is exact (not the single-pool approximation) because per-cover heterogeneity is captured inside Abar.
- PROOF OF NO COVER-BY-COVER REPETITION & PERFORMANCE NEUTRALITY: exactly one cover is emitted per slot, and v_c cancels in Abar (sum_c A_c v_c / sum_c v_c is invariant to scaling all v_c), so performance changes ONLY which rendition is chosen, never the song's frequency — exactly the user's 'performance = better rendition, not played more often'.
- COVER PICK: within the chosen unit, weighted_choice over covers with weight A_c * v_c (so a just-played rendition, low song_cooldown, is suppressed; a hot-group rendition is suppressed via base_score; better/original renditions favoured). Finite-guard + uniform fallback on sum<=0.
- COLD START AT UNIT LEVEL: cold_start_candidate_indices and cold_start_is_active operate on UNITS. first_coverage = units with >=1 cover that has repeat_count<1 AND is unrated; the unit leaves first_coverage after ONE play (song-level coverage, matching user intent). During a first_coverage unit, the within-set cover pick is RESTRICTED to its uncovered covers (deterministic spread of first exposure). second_coverage uses unit repeat_count<2; played-twice threshold = len(units)/2.
- FALLBACK LADDER (unit level): if sum_u W(u) over the candidate units <= 0 -> recompute A_c with disable_group_and_sub_cooldowns and UnitCooldown=1; if still <=0 -> also disable_song_cooldown; final tier is weighted_choice's uniform pick. Mirrors algorithm.py:364-406 but at the unit layer.
- RESOLUTION: the chosen cover is a concrete Track.id, satisfying the NOT-NULL PlaylistItem.track_id FK and keeping m3u8/playback-events/load_run_response unchanged. Gate the whole two-level path behind cover_two_level_enabled (default True) with the legacy per-cover path retained.
- BACKWARD-COMPAT: with no sub_groups every unit is a singleton, L=1, Abar=A_c, UnitCooldown=1, within-set pick is trivial, so W(u) reduces to today's score except rating_multiplier is now the normalised overall — a golden parity test on a no-ratings/no-sub_group library yields identical seeded runs.

## Comparison UX

- ACTIVE DETECTION (not literally screen-on): usePlayer keeps a localStorage ring buffer (harmonica.activity.v1) of the last cover_comparison_active_window (5) PLAYED songs, each tagged rated? if a star was submitted for it during/after play (hooked off rateTrack/App.tsx:295 and finishTrack). active = (#rated in window >= cover_comparison_active_min_rated, 4). Measured on songs played, not wall-clock, so a locked screen doesn't reset it. This is SEPARATE from the backend ui_active flag (which means web-UI-open -> visual_priority) — do not overload it.
- FOREGROUND GATE (resolves the 'pocket plays two covers back-to-back' blocker): A/B is scheduled ONLY when document.visibilityState==='visible' (existing visibilitychange wiring at usePlayer.ts:326) AND active AND an eligible set exists AND throttle elapsed. If the screen isn't on, fall back to ordinary single-cover selection and schedule nothing.
- ELIGIBILITY: cover_set_state.comparison_phase != 'settled' AND n_covers >= cover_comparison_min_covers (4) AND >= cover_comparison_cooldown_songs (3) songs since this set's last comparison. Below 4 covers or settled: no A/B, the algorithm just rotates renditions via the unit cooldown.
- INJECTION (explicit override, NOT emergent): when conditions hold, after the current song the client requests GET /cover-comparisons/next?set=<sub_group> (server runs BT pair selection) and SPLICES cover A then cover B of that set as two consecutive QueueItems flagged {comparison:{setId, peerTrackId, role}}. The pair deliberately bypasses the unit cooldown — A/B is documented as an override of the anti-repetition rule, not a product of it.
- PROMPT: A plays to its end (or user-advance); B starts; partway into B (B reaches ~25% OR 20s) a NON-BLOCKING bottom sheet (BreakModal pattern, App.tsx:449) asks 'Which was better? [A] [B] [About the same]' plus 'Replay A briefly'. It never pauses B and auto-dismisses if ignored — an unanswered pair RECORDS NOTHING and schedules no follow-up (abort, don't repeat).
- REPLAY-A on the SINGLE element (never a 2nd <video>, which would break the createMediaElementSource loudness meter + videoStage reparenting): save peek={trackB, time, pct=time/durB}; load A's media into the shared element, seek to pct*durA, play cover_comparison_replay_seconds (8s), then restore B at peek.time and resume. Implemented as a transient 'peek' mode using usePlayer.seek (usePlayer.ts:447). Bump SESSION_KEY 'harmonica.session.v2'->v3 (QueueItem gains comparison) or restored sessions load malformed.
- VERDICT PERSISTENCE: POST /cover-verdicts {sub_group, track_a_id, track_b_id, winner_track_id|null, pct_a, pct_b, session_id, run_id} -> insert cover_comparisons row, then REFIT Bradley-Terry for the set and update cover_rendition_state.bt_strength/comparison_count and cover_set_state.total_comparisons. New api.ts method using the tolerate-404 capability pattern (api.ts:135-152). NOT a playback event (the fixed started/paused/skipped/completed union stays clean for skip/completion stats).
- RANKING = regularised Bradley-Terry MAP per set (new bt.py): P(i beats j)=pi_i/(pi_i+pi_j); fit by MM/Zermelo with a phantom-average-player Gaussian prior (alpha=cover_bt_prior_strength=1.0 pseudo-comparisons vs a virtual average) so undefeated/winless covers and disconnected comparison graphs stay finite; Davidson tie term for 'about the same'; refit from ALL raw verdicts (order-independent). bt_strength_c = log(pi_c) - mean(log pi). Performance is RELATIVE within-set — never written as an absolute 0..5 star.
- PAIR SELECTION (minimise total comparisons, don't re-pick the same two): score each pair (i,j) by p_ij*(1-p_ij)/(comparison_count_i + comparison_count_j + 1) from current BT (p(1-p) maximised at adjacent/most-uncertain pairs; denominator favours under-sampled covers). Pick argmax excluding the immediately previous pair.
- REVERT-TO-STARS / TERMINATION: cover_set_state -> 'bootstrapping' while eligible; -> 'settled' when every cover has >= cover_comparison_min_per_cover (3) comparisons AND the adjacent BT log-strength gaps exceed their standard error (stable beyond noise) OR total_comparisons >= cover_comparison_max_total (40, hard ceiling guaranteeing termination for near-equal/intransitive covers). On settle: freeze bt_strength, stop prompting, performance becomes an editable star (StarRating already renders it on sub_group tracks); a user star edit becomes authoritative and suppresses BT writeback; an explicit 'Compare again' resets to 'bootstrapping'.
- RENDERING: user's own stars stay INTEGER (raw). Derived overall (50/50) and BT-derived performance and the optional normalised effective are FRACTIONAL — add half/partial-star fill ONLY for those secondary/derived displays (StarRating/MiniRating are integer-only today at App.tsx:1410-1414,1203). A 'Versions' panel in the track editor shows the set in BT order. StatsView surfaces normalisation readiness (coverage/depth) and 'A/B available' using existing rated_track_count/track_count.
- WHY-THIS-SONG: add explanation keys + format.ts whyReasons entries + a new WhyReason.icon enum value + WhyIcon case for cover_log_factor ('1 of 6 versions, weighted on a log curve'), cover_selection ('top-rated rendition by A/B'), original_prior. Mind the 4-reason cap (format.ts:108).

## Settings

- rating_normalization_enabled — boolean, default true, switch (section 'Rating normalisation'). 'Strip mood swings from ratings by averaging your repeat ratings and gently regressing outliers, once enough of your library is rated. Off = use your latest star as-is.'
- rating_outlier_sd — number(float), default 1.0, slider min 0.25 max 3.0 step 0.25. 'How far one rating may stray from that song's own average before it is pulled back in. Lower is stricter.' (FLOAT default mandatory or sanitize_value rounds it.)
- rating_session_mood_correction — boolean, default true, switch. 'Correct a whole rating session that ran uniformly generous or grumpy (only once your library is well-rated).'
- rating_session_min_songs — number(int), default 10, stepper min 5 max 50 step 1. 'Minimum songs rated in one sitting before session-mood correction can apply.'
- rating_coverage_ready_fraction — number(float), default 0.6, slider min 0.2 max 1.0 step 0.05. 'Fraction of rateable songs that must have a rating before library-wide normalisation switches on.'
- cover_two_level_enabled — boolean, default true, switch (section 'Covers'). 'Pick a song first, then its best rendition — instead of treating every cover as a separate track.'
- cover_log_base — number(float), default 4.0, slider min 2.0 max 20.0 step 0.5. 'How much extra play a song earns for each extra cover, on a log curve. Lower = covers add more. Default: 2 covers about 1.5x, 10 about 2.7x, and 10 barely beats 9.' (Clamped >1 in code.)
- cover_original_prior — number(float), default 0.05, slider min 0.0 max 0.3 step 0.01. 'Small head-start the original rendition gets when choosing which cover to play; fades as you compare more.'
- cover_comparison_enabled — boolean, default true, switch. 'Offer A/B which-was-better comparisons for songs with many covers while you are actively rating and the screen is on.'
- cover_comparison_min_covers — number(int), default 4, stepper min 2 max 12 step 1. 'Minimum covers a song needs before A/B comparison is offered.'
- cover_comparison_active_window — number(int), default 5, stepper min 3 max 10 step 1. 'How many recently-played songs the actively-rating check looks at.'
- cover_comparison_active_min_rated — number(int), default 4, stepper min 1 max 10 step 1. 'How many of those recent songs must be rated to count as actively rating (the 4-of-last-5 rule).'
- INTERNAL config.Settings fields (defaults only, NO SettingDefinition, kept off the settings page to avoid a wall of statistical dials): rating_shrinkage_pseudocount=1.0, rating_min_multi_rated_songs=20, rating_min_samples_for_sd=30, rating_session_bias_min_sd=0.5, rating_session_bias_pseudocount=10.0, cover_perf_min_multiplier=0.7, cover_perf_max_multiplier=1.4, cover_bt_prior_strength=1.0, cover_comparison_min_per_cover=3, cover_comparison_max_total=40, cover_comparison_cooldown_songs=3, cover_comparison_replay_seconds=8.0.
- PLUMBING (per landmine, do together or GET/POST /settings break): each USER-FACING key needs a config.Settings field (float defaults for fractional knobs) + a SettingDefinition in SETTING_DEFINITIONS + a SettingsRead field + an entry in playlist.settings_snapshot (run provenance) + the closed TS unions SettingControl.key/AppSettings in web/src/types.ts; add two new SETTING_SECTIONS ('Rating normalisation', 'Covers') in App.tsx so they group instead of landing in 'More'. Decide per-PRESET whether to set the new keys (default: leave at defaults).

## App-wide observations (bugs & opportunities found)

- ensure_additive_* helpers are wired only into api.create_app and scripts/import_storage_library.py; cli.py and scripts/seed_demo_library.py call init_db() but NOT the helpers, so ANY new column on an existing table is silently missing there today. Moving the helpers into init_db() fixes a whole latent class of bugs beyond this feature.
- variant_counts (playlist.py:49-55 and api.py) is computed library-globally and ignores included_track_ids, so device-scoped profiles already get wrong cover counts and wrong applies_to_variants_only gating — a pre-existing bug this work must fix anyway.
- Song-level and group-level rating use effective_rating independently today; unifying them onto one normalised per-unit overall (this design) is a coherence win that also stops covers inflating group weight linearly.
- StarRating/MiniRating are integer-only; the app has no fractional star rendering, which blocks any derived/normalised/performance display — a latent UI limitation worth solving once, cleanly.
- whyReasons caps at 4 and uses a closed icon union; new cover/normalisation reasons compete for those slots, so the explanation surface needs deliberate prioritisation, not just additions.
- Session persistence validates only Array.isArray(queue) under a single SESSION_KEY; any QueueItem shape change (A/B pair) silently loads malformed items unless the key is bumped — fragile by design.
- PATCH /tracks ratings carry no session/run context at all; this is a structural gap for ANY temporal rating analytics (session-mood is just the first consumer). A first-class rating_session_id is broadly useful.
- Two divergent 'rated' notions (history.rated_track_ids = any TrackRating.value vs effective_rating None) plus cold_start_multiplier checking both is brittle; keeping BT performance out of rating_samples (this design) prevents a new inflation of the 'rated' stat, but the underlying duality should be cleaned up.
- harmonica_algorithm_spec.md section 7 still documents a stale 0-10 rating model (m_s=0.5+R/10, factors incl. 'message'/'replayability') that contradicts the implemented 0..5 piecewise ratings.py — it should be annotated as superseded to stop future agents anchoring to it.
- The live spec doc promises an 'appended math/schema section' that does not exist; this blueprint is that section and should be committed into docs/planning/rating-normalization-and-covers.md.
- The single <video> element bound to one createMediaElementSource (loudness meter) + videoStage/videoPark reparenting is a load-bearing constraint every future playback feature (including A/B) must respect — worth documenting prominently.
- The user's 'cold start should guarantee coverage' intent is only a boost today; redefining coverage at the UNIT level here is the natural moment to make song-level coverage a real, testable guarantee.

## Residual risks

- Normalisation stays INERT until the depth+coverage thresholds are met; on a mostly-rated-once 250-song library the headline feature does little at first. Mitigation: surface readiness (coverage + #multi-rated) in StatsView so the warming-up period is legible; backfill keeps it safe (n=1 -> inert).
- Two-level generate_playlist is a genuine rewrite of the app's one differentiator (all cooldown/cold-start/repeat-credit state and the 3-tier fallback). Regression risk to the working anti-repetition guarantees. Mitigation: gate behind cover_two_level_enabled, keep the legacy path, ship golden seeded parity tests for no-sub_group libraries.
- Lazy per-generation normalisation adds a rating_samples query + O(samples) compute and a per-slot unit-grouping pass; trivial at ~250 songs/length 1000 but scales with library x samples x length — watch if the library grows large.
- BT refit per verdict and per generation is O(comparisons) per set; fine at expected volumes but unbounded if comparison counts balloon — the max-total ceiling and settle also bound this.
- A/B gating depends on client signals (visibility, active ring buffer); a mis-tuned throttle could feel naggy or never fire. Mitigation: all thresholds are settings, abort-on-no-verdict, foreground-only.
- rating_session_id is client-supplied; a missing/spoofed id degrades session-mood to created_at day-bucketing (acceptable, documented).
- is_original_rendition is user/inferred; if unset the original prior is simply inert (safe) but a desired nicety is dormant until curation — surface unflagged sets in stats.
- Export/import deliberately renormalises against the target population (SD is library-wide); importing into a partial/device library yields different effective values by design — must be documented so it isn't read as data loss.
- Even grouped into two sections, ~12 new controls make the Covers/Normalisation settings denser than the rest of the app; the internal-constants split mitigates but the surface still grows.
- Winsorise at k=1 only meaningfully bites at n>=3 asymmetric series; the real small-n work is done by shrinkage. If a user disables shrinkage (or it stays a fixed pseudocount), n=1..2 denoising is limited — communicate that normalisation strengthens as songs are re-rated.
- Fractional star rendering plus the SESSION_KEY v3 bump touch hot UI paths; a missed bump loads stale sessions and integer-only widgets mis-render derived values — covered by tests but easy to regress.

## Verification strategy

- Unit: pooled within-series sigma_f on a synthetic library with KNOWN within vs between variance recovers the within-song scale, not the (much larger) total SD.
- Unit: winsorise+shrink behaviour — n=1 shrinks halfway to mu_f (pseudocount 1); a symmetric n=2 pair is NOT a no-op (shrinkage moves it); a single outlier in an n=5 series is clipped to mu_c +/- k*sigma and the mean moves toward mu_c.
- Property: every effective value in [0,5]; an unrated or cleared/retracted (cover,factor) yields None -> rating_to_song_multiplier(None)=1.0 (neutral path preserved).
- Unit: overall = 0.5*direct + 0.5*mean(others) with NO double-count — raising one sub-factor by d moves overall by exactly 0.5*d/|others| and the song multiplier by the intended (not 1.5x) amount; assert sub-factors are counted exactly once.
- Unit: session-mood recovers a synthetic +1.0 generous bias ONLY when >= the qualifying-songs minimum have out-of-session history; returns 0 for an all-first-rating session (cold-start safety).
- Property (Monte-Carlo over many slots): a unit's marginal selection frequency scales as 1+log_base(n) and is otherwise independent of n — compare 1/2/9/10-cover units; assert '2 not 2x' and '10 barely > 9'.
- Property: exactly one cover emitted per slot; no two covers of a set are adjacent outside A/B mode; performance changes which cover but not the set's total exposure.
- Golden parity: a seeded library with no sub_groups and no ratings produces byte-identical runs on the legacy vs two-level path (rating_multiplier=1.0 both).
- Unit: cold start at unit level — a 7-cover unit leaves first_coverage after ONE play; the played-twice threshold uses len(units)/2; first-play cover pick is restricted to uncovered covers.
- Unit: feed a NaN/inf score and assert weighted_choice degrades to a uniform distribution (not always-last); assert mean-of-empty paths return 0/None as specified.
- Unit (bt.py): undefeated and winless covers get finite strengths; a disconnected comparison graph still yields a global order; 'about the same' ties handled (Davidson); refit is order-independent across verdict permutations; settle terminates at the max-total ceiling for near-equal covers.
- Integration: a device-scoped library uses scoped n_covers for L(n) and applies_to_variants_only, while sigma_f/readiness remain whole-library.
- Migration: open a copy of the real ~250-song DB, run init_db() -> is_original_rendition added, backfill inserts one 'import' sample per existing rating, GET /settings and a generation succeed, normalisation reports inert.
- Web: A/B fires only when visible AND active AND eligible AND throttle-elapsed; an ignored prompt records nothing and schedules no follow-up; replay-A reuses the single <video> element and the loudness meter still reads; restoring a v3 session works and a v2 session is discarded cleanly.
- Round-trip: export then import on a PARTIAL library; caches are recomputed (not trusted), is_original preserved, session/run ids stripped.
- Gates: ~/.local/bin/uv run pytest -q, ~/.local/bin/uv run ruff check src/harmonica tests, and cd web && npm run build all green; a settings-coupling test asserts every SettingDefinition key has a matching Settings attribute and SettingsRead field.

## Phased implementation plan


### Phase A — Rating history + lazy normalisation core (winsorise+shrink+readiness+ramp, overall 50/50, unified song/group rating)

**Deliverables:** rating_samples table + idempotent backfill; init_db() wiring of ensure_additive_* helpers; upsert_ratings appends a sample (still upserts raw TrackRating.value); new normalization.py (per-factor stats, per-(cover,factor) effective, unit aggregation, overall 50/50 with no double-count); load_algorithm_inputs computes/caches stats and threads the normalised per-unit overall into AlgorithmTrack.rating_multiplier; aggregate_group_rating_multipliers refactored to consume the same per-unit overall; TrackRead.ratings_effective optional; finite/mean-of-empty guards.

**Files:** `src/harmonica/models.py, db.py, api.py (upsert_ratings, schemas), normalization.py (new), ratings.py, playlist.py, schemas.py, tests/test_normalization.py`

### Phase B — Session-mood correction + session attribution

**Deliverables:** rating_samples.session_id; leave-session-out, qualifying-songs-only, shrunk, thresholded bias; client rating_session_id ('sitting' id) on PATCH /tracks and a dedicated POST /tracks/{id}/ratings; inert during cold-start sessions.

**Files:** `src/harmonica/normalization.py, api.py, schemas.py, web/src/{usePlayer.ts,api.ts,App.tsx,types.ts}, tests/test_session_mood.py`

### Phase C — Two-level cover selection + log cover-count + unit cold-start + device-scope fix + settings

**Deliverables:** generate_playlist two-level loop (unit grouping, L(n) exposure, Abar, within-set pick, unit-level cold-start and 3-tier fallback, finite guards); AlgorithmTrack new frozen fields; n_covers/units computed after included_track_ids; tracks.is_original_rendition column + UI toggle + import inference; the 12 user-facing settings + internal config fields; why-this-song keys; cover_two_level_enabled gate + golden parity test.

**Files:** `src/harmonica/algorithm.py, playlist.py, models.py, config.py, settings_store.py, schemas.py, scripts/import_storage_library.py, web/src/{App.tsx,types.ts,format.ts,presets.ts}, tests/test_two_level_selection.py`

### Phase D — Cover-comparison data model + Bradley-Terry

**Deliverables:** cover_comparisons, cover_rendition_state, cover_set_state tables; bt.py (regularised BT MAP + Davidson ties + phantom prior); POST /cover-verdicts (refit + update caches); GET /cover-comparisons/next (D-optimal pair selection); perf_mult derivation feeding within-set v_c; settle/revert lifecycle + max-total ceiling.

**Files:** `src/harmonica/models.py, bt.py (new), api.py, playlist.py, serialization.py, tests/test_bradley_terry.py, tests/test_cover_lifecycle.py`

### Phase E — Comparison UX (consecutive playback, replay-A, active detection, fractional stars)

**Deliverables:** usePlayer A/B orchestration (foreground+active+eligible+throttle, splice pair, abort-on-no-verdict), replay-A peek on the single element, active ring buffer (localStorage), SESSION_KEY v3; non-blocking verdict modal; postCoverVerdict/nextComparison (tolerate-404); fractional star rendering for derived/effective values; Versions panel; two new settings sections.

**Files:** `web/src/{usePlayer.ts,App.tsx,api.ts,types.ts,format.ts}`

### Phase F — Serialisation round-trip + readiness/curation surfaces

**Deliverables:** export/import rating_samples (strip session/run ids), cover_comparisons, cover_rendition_state, cover_set_state, is_original_rendition; recompute caches on import; StatsView normalisation-readiness (coverage+depth) indicator; CurateView surface for unflagged cover-set originals; settings_snapshot provenance for new tunables.

**Files:** `src/harmonica/serialization.py, api.py, web/src/{App.tsx,CurateView.tsx,types.ts}, tests/test_serialization_roundtrip.py`

### Phase G — Hardening, docs, polish

**Deliverables:** ramp tuning, preset decisions, reconcile the two 'rated' notions, annotate stale harmonica_algorithm_spec.md section 7, append the finalised math/schema into docs/planning/rating-normalization-and-covers.md, full pytest+ruff+web build.

**Files:** `docs/planning/rating-normalization-and-covers.md, harmonica_algorithm_spec.md, src/harmonica/history.py, tests/`
