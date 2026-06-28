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
