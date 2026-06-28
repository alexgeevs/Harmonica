# Harmonica Algorithm Roadmap

Output of a multi-agent brainstorm (7 ideation lenses) + adversarial value/feasibility vetting of
35 ideas + synthesis (2026-06-27). Items are vetted survivors only; rejected ideas and why are at the
end so they're not re-proposed. Authored by the agent fleet; the user reviews & prioritises.

## Cross-cutting principles (from the review)

- Repair before you add: the single highest-value change is fixing the permanent skip-penalty max() (history.py:62) and the crude 3-bin listened_fraction step (history.py:89-102) BEFORE layering new scoring terms — every implicit-feedback idea sits on top of these and inherits their bugs.
- One pattern carries almost all feasibility: every kept selection-time term is a bounded, floored, strictly-positive multiplier dropped into the score_track product (the prev_compressed / cold_start pattern, algorithm.py:265-274). Because cooldowns multiply to ~0 right after a pick and the fallback ladder requires sum(scores)>0, these terms can soften or boost but can NEVER break the anti-repetition guarantee.
- Keep the displayed rating sacrosanct. The shipped invariant (displayed = plain fractional average; internal normalised value is separate) must hold: all behavioural/derived utility goes into NON-rating multiplier slots (history_multiplier, new dedicated multipliers), never into rating_multiplier, so the 'magic' never leaks into the number the user sees.
- Reuse the discipline already shipped in normalization.py: empirical-Bayes shrinkage, the readiness/alpha ramp, min-sample gates, and 'confidence-before-explanation'. Apply the same rigour to every new derived signal so small-data noise stays inert by construction.
- Selection vs playback are different layers. A loudness jolt is cured by playback-time gain matching, not by reordering the queue; don't pay selection utility to fix a problem you can gain-match away.
- Prefer dense, deterministic signals over sparse learned graphs at a few-hundred-song scale: co-membership, loudness/energy, and completion ratio are available now and self-explaining; anything that needs many sessions of sequence data to mean anything (EWMA type graphs) is cold for a long time and prone to feedback loops.
- A handful of shared primitives unlock a whole cluster of features and should be built deliberately first: an injected now-clock (determinism + wall-clock features), session segmentation by time-gap, and an intrinsic per-song energy/loudness aggregate.
- Steering should be ephemeral and honest: persistent taste lives in ratings; in-the-moment intent ('not now', focus/discovery, stations) lives in session-scoped multipliers that decay and never log as a quality signal.

## Seed-idea verdict (user's type-link + simple-average ideas)

Seed 1 (weak cross-song type link + anti-two-in-a-row): MOSTLY ALREADY BUILT — endorse the intent, don't re-architect it. The 'good rating raises that type's standing' half ships today as aggregate_group_multipliers_from_overall (normalization.py:420) gated by enable_group_rating_multiplier with group_rating_min/max_multiplier as real controls; the 'still space two of a type apart' half ships as the per-group linear_recovery cooldown plus apply_clustering_bias; and 'songs can have several types at once' ships as fractional multi-group membership (normalized_membership_shares). So the user's idea is correct and largely realised. The two concrete next steps: (a) VERIFY and EXPOSE the group-rating multiplier as an explained, tunable setting and add it to the 'why this song' string so the long-run type lift is visible; (b) the only genuinely-new safe increment is the static co-membership type-affinity coherence (roadmap item 'Type-affinity coherence'), folded into the existing group_clustering_bias as one 'mood coherence' slider defaulting to off — NOT a learned sequence-EWMA graph (feedback-loop trap, cold for a long time). Net: ship (a) now as part of explainability, ship (b) later, and explicitly reject the learned-graph version. Seed 2 (keep the user-facing rating a simple average): STRONGLY ENDORSE — already implemented and correct. plain_rating_averages() feeds the displayed fractional average, outliers are judged against that series mean, and the internal normalised 'magic' value (ratings_effective) is separate and seen only by the algorithm. The load-bearing invariant the rest of the roadmap must protect: NO derived or behavioural value (provisional ratings, completion arm, exploration boost) may ever write into the displayed average — which is exactly why the new positive behavioural signal lives in history_multiplier and dedicated multipliers, never in rating_multiplier. Keep it simple on the surface, keep the magic internal, and never let the two cross.</seed_idea_assessment>
</invoke>


## Quick wins

- Fix the permanent skip-penalty max() (history.py:62) and the 3-bin listened_fraction step (history.py:89-102) — bug-grade, ~S, and it de-risks every other behavioural feature. One accidental skip currently floors a song at 0.2x forever.
- Add song_cooldown and the top group's cooldown to whyReasons (web/src/format.ts) — the highest-trust anti-repetition messages are computed but never shown.
- Ship the forgetting-curve rediscovery multiplier — feas 5, a single bounded term into the existing score_track product, captures created_at which is stored but unused in scoring.
- Lifetime play-count equity brake with an ABSOLUTE floor + rating-awareness — one line into final_score, repeat_count already plumbed end-to-end, default off so it can't perturb tuned behaviour until opted in.
- Inject a now-clock provider into generate_playlist — tiny, keeps the queue deterministic under seed, and unblocks rediscovery plus any future wall-clock feature.
- Build the session-segmentation utility once — cheap read-side clustering that pays off in stats, break reminders, the completion-arm gate, and the re-rate prompt.

## NOW (3)

### Repair & smooth the implicit-feedback signal (skip-penalty + listened-fraction map)  ·  effort S
**Why.** history.py:62 keeps skip_penalty as a permanent max() over ALL events, so one accidental <10% skip floors a song at 0.2x forever; and playback_event_signal (history.py:89-102) is a 3-bin step that throws away skip POSITION (a 0.95 skip and a 0.55 skip both score 0.75 credit). These are the foundation every other behavioural idea stands on.

**How.** In history.py replace the recency-blind max() with a count- and recency-weighted aggregate (or a Beta(a,b) where a clear early-skip only counts toward dislike when it RECURS across distinct sessions). Replace the 3-bin map with a smooth continuous curve from listened_fraction -> (repeat_credit, penalty), treating >=~90% as a near-completion (full credit, ~zero penalty). Feeds the existing history_multiplier and repeat_credit; no schema change (PlaybackEvent.progress_seconds/duration already present).

**Settings.** skip_penalty_strength (exists); add skip_penalty_halflife / recency window.

**Dependencies.** Session segmentation primitive (for distinct-session recurrence gating).

### Surface cooldown reasons in 'why this' + on-demand 'why isn't X playing?' pull  ·  effort S
**Why.** format.ts whyReasons already ranks groups/rating/cold-start/visual but NEVER surfaces song_cooldown or the top group cooldown — the most intuitive, highest-trust anti-repetition messages ('you heard this exact song ~N ago', 'eased off this type'). And the real distrust trigger ('it never plays X') has no answer today.

**How.** Extend whyReasons (web/src/format.ts) to template ex.song_cooldown and the dominant group's cooldown. Add a PULL endpoint 'why isn't <song> playing?' that recomputes that one track's live score_track breakdown against current queue state and names its argmin multiplier in plain language, guarded so it only blames a suppressor when the song was a genuine contender (base_score in top quartile AND one multiplier dominates the gap) — otherwise answers honestly. Pure post-processing; no selection-path change.

**Settings.** Optional low-n confidence note threshold (e.g. n_samples<3).

**Dependencies.** None.

### Forgetting-curve rediscovery boost for dormant favourites  ·  effort M
**Why.** Every recency term today is ordinal event-count distance and purely suppressive; created_at is stored but never used in scoring. There is no positive, wall-clock term to resurface a genuinely loved song you haven't heard in months. Highest-feasibility serendipity win.

**How.** New rediscovery_multiplier folded into the score_track product (algorithm.py:265-274): 1 + gain * is_favourite * (1 - exp(-days_since/tau)). days_since from the most recent PlaybackEvent.created_at, captured inside the existing summarize_history pass (zero extra queries). is_favourite = soft gate on normalised overall above the library mean (rating is a GATE, not a magnitude, to avoid double-counting rating_multiplier). Cap <=1.5; only fires for tracks with >=1 play (cold-start owns never-played). Express dormancy relative to library cycle time so it stays inert for a regular listener and never fires on the whole library at once. Collapses to 1.0 the moment the song plays.

**Settings.** rediscovery_strength slider + enable toggle (tau internal ~60d or cycle-relative).

**Dependencies.** Injected now-clock provider (determinism); normalised overall_by_track (shipped).

## NEXT (8)

### Two-sided history multiplier: positive completion arm for under-rated songs  ·  effort M
**Why.** history_multiplier is strictly <=1.0 (history.py:146-150) — the algorithm can only ever PUNISH a skip, never convert consistent completions/replays into standing. A low-effort user who rarely rates stays near-uniform forever. This is the missing positive behavioural channel.

**How.** Extend history_multiplier with a small positive arm up to ~1.15 driven by the EB-shrunk completion-vs-skip ratio, shrunk toward the library-wide completion rate so a never-at-risk song sits neutral. Gate the positive arm on completions spanning N DISTINCT sessions/days (not back-to-back lean-back plays), suppress it entirely while cold_start_active, cap tighter than explicit ratings, and override the instant an explicit rating exists. Add an explicit 'replayed' event_type (additive String value) as a stronger positive input. Stays in the history_multiplier slot — NEVER rating_multiplier — so the displayed average is untouched. Surface as its own line ('you finish this often').

**Settings.** completion_reward_strength (mirrors skip_penalty_strength) + enable toggle.

**Dependencies.** Item 1 (smoothed signal); session segmentation; explicit-replay event from the player.

### Lifetime play-count equity brake (merit-relative)  ·  effort S
**Why.** All anti-repetition today is short-horizon recency that fully resets; there is zero cumulative fairness term, so high-weight songs win the lottery repeatedly while the mid-tail starves between cold-start passes. Cheapest possible additive fix (repeat_count already in hand).

**How.** familiarity_multiplier = 1/(1 + lambda*log(1 + max(0, plays - expected_plays))) into the score_track product, using repeat_count from TrackHistorySignal. Key on plays-IN-EXCESS-of-merit, not raw count: expected_plays derived from the song's normalised rating/weight, with an ABSOLUTE floor k (~3-5) so the under-played majority is provably untouched. Make it rating-aware (skip/halve the brake for top-rated songs — a beloved 5-star played 40x is working as intended) and floor the multiplier (~0.4) so nothing is ever banned. Gate active only after cold-start completes.

**Settings.** overplay_strength (default 0 = off).

**Dependencies.** Cold-start phase flag (exists); normalised rating.

### Low-evidence exploration boost (deterministic, cold-start continuation)  ·  effort S
**Why.** cold_start is a one-time hard gate (history.py:153) — once a song gets ANY rating it falls out of the learning loop forever, even with one noisy sample. The genuine gap is 'give under-tried songs a fair second look' without the non-determinism and 'random feeling' of Thompson sampling.

**How.** Extend cold_start_multiplier from a binary gate into a continuous decaying boost = 1 + c/(1 + plays + rating_samples), capped and decaying smoothly to 1.0; OR equivalently a UCB-style optimism term m_i + kappa*sqrt(v_i) feeding rating_multiplier. Deterministic (no rng through score_track) so the queue stays reproducible and the why-panel is honest ('barely explored, giving it a look'). Passes through all cooldowns; scoped to after cold-start coverage so it can't starve the guarantee; capped so it can't resurrect a genuine 1-star.

**Settings.** exploration_strength (default low/off).

**Dependencies.** rating_samples count (shipped); cold-start.

### Hierarchical empirical-Bayes shrink target (cover-family -> type -> grand mean)  ·  effort M
**Why.** normalization.py:134 shrinks every sparse song toward the single factor grand mean — the least-informative prior. A new track resembling the user's favourite types/cover-families deserves a warmer start. Uses the user's OWN curated similarity graph (groups/sub_group), no embeddings.

**How.** In series_effective replace the single shrink target stats.mu with a precision-weighted fallback chain: sub_group (cover-family) mean -> fractional-share-weighted weight-group means -> factor grand mean, each used only to the extent it has support. Reuses existing per-factor stats and the group aggregates already computed for group multipliers (normalization.py:420). Strictly an INTERNAL prior (displayed average untouched); gated behind the existing alpha readiness ramp; cold-start floor stays independent so a low-predicted unrated song is never pushed below its coverage guarantee.

**Settings.** content_prior_strength (default modest; 0 = today's grand-mean shrink).

**Dependencies.** Shipped normalization pipeline; group/sub_group membership.

### Lyric-dense breather (anti-consecutive cognitive load)  ·  effort S
**Why.** Spacing out attention-demanding tracks is a real anti-fatigue axis distinct from type/format/loudness spacing, and the user gestured at it. The full leaky-bucket attention model is over-engineered for the data; the cheap robust slice captures most of the value.

**How.** Add has_lyrics to AlgorithmTrack (additive). Mirror avoid_consecutive_compressed exactly: track a prev_lyric_dense run-length counter in the generate_playlist loop and softly downweight further has_lyrics candidates after 1-2 consecutive lyric-dense plays (selection-time only, uniform-safe so it can't stall generation, recovers to neutral the moment one instrumental plays). Explicitly DROP the novelty/inverse-play-count term (it fights cold-start) and the focus-rating input (too sparse).

**Settings.** lyric_breather_enabled + lyric_breather_strength.

**Dependencies.** has_lyrics signal on the track.

### 'Not now' ephemeral session steering (suppression only)  ·  effort M
**Why.** Today the only honest signals are a permanent rating (deliberately slow/mood-clean) or a logged skip (a quality signal). There is no low-commitment, reversible 'not in the mood, move on' that doesn't pollute the long-run model. Genuine missing primitive.

**How.** An in-memory per-run steer map {song_id/sub_group -> multiplier} decaying to 1.0 over N slots. On tap, regenerate the UNPLAYED TAIL of the current PlaylistRun, passing a session_steer_multiplier into score_track. Suppress the song + its sub_group ONLY (not the broad group — avoids small-data starvation and the anti-consecutive conflict). Floor >=0.05 and strictly multiplicative on top of cooldowns so it can never override the anti-repetition guarantee. Make it mutually exclusive with logging a skip for that slot. CUT the symmetric 'More like this' type-boost (contradicts the anti-same-vibe thesis); if a positive control is wanted, restrict it to a bounded sub_group-only relaxation.

**Settings.** steer_strength + decay_length N.

**Dependencies.** A queue-tail regeneration endpoint (new); session concept.

### Session segmentation primitive (time-gap clustering)  ·  effort S
**Why.** Multiple features need a real notion of 'session' that doesn't exist yet (history.py has no time boundary). Building it once as a shared utility unlocks a cluster of work and improves stats and break reminders.

**How.** Cluster PlaybackEvents by created_at gap (>~30min = new session) as a read-side utility. Powers: cross-session cooldown context, accurate stats ('12 sessions this week, avg 47min'), hearing-health break reminders, distinct-session gating for the completion arm, and the re-rate prompt's 'one ask per session' guard. No schema change.

**Settings.** session_gap_minutes (default ~30).

**Dependencies.** None. Enables items 4, 11, 13.

### Playback-time loudness normalization (ReplayGain-style)  ·  effort M
**Why.** The correct cure for the +9dB lunge-for-volume is gain-matching at PLAYBACK, not reordering the queue. Doing it here removes the jolt without ever skewing selection (which would down-weight a well-rated ballad just because the next-best candidate is hot).

**How.** Compute each track's running-median avg_level (and peak for crest) from PlaybackEvent telemetry (normalised by output_gain so it measures intrinsic loudness, not session volume); target a reference level and nudge output_gain at play time. NOT a score_track term — a player/playback-layer change. Require a minimum sample count before trusting a track's median; inert (uniform) when the library has no loudness data. Explainable: 'matched levels, -4dB on this track'.

**Settings.** loudness_normalization_enabled + target reference level.

**Dependencies.** Existing avg_level/peak_level + output_gain telemetry.

## LATER (8)

### Recency-weighted rating samples (age decay of effective count)  ·  effort M
**Why.** The normalisation pipeline is time-blind: a two-year-old single 5-star counts exactly like a fresh one. Tastes drift; an opinion's TRUST should fade with age (not its value be silently rewritten).

**How.** Weight each sample w_i = 0.5^(age_months/halflife) and use n_eff = sum(w_i) in the existing shrink (shrink = n_eff/(n_eff+pseudocount)) and as the weight in the winsorised mean — one mechanism, additive at normalization.py:133. Floor the decay so a stale rating never shrinks PAST where a fresh n=1 rating sits (age reduces trust toward 'one fresh sample', never inverts past the mean to bury a favourite). Explicitly EXCLUDE the plays-since-rating axis — completions are confirmation, not staleness. Displayed plain average stays untouched.

**Settings.** rating_halflife_months (default long ~24 = near-inert/opt-in).

**Dependencies.** Shipped normalization; rating_samples.created_at (shipped).

### Opportunistic re-rate prompt (active learning, pull not push)  ·  effort M
**Why.** Once a song has one noisy/stale rating it is invisible to the learning loop, even though re-asking (rather than silently mutating the number) is the honest way to resolve drift. Feeds the normalisation layer everything else depends on.

**How.** Surface a gentle 'still a 5?' prompt ONLY for the song that JUST FINISHED (>50% — rateability is a hard gate) AND is low-confidence: few samples OR normalization marks its overall not-ready/heavily-shrunk OR it is stale OR behaviour now contradicts the stars (recent skips on a once-high-rated song). Cap one prompt per session, dismissible, never re-ask a declined song. Strictly DISPLAY-side — never feeds scoring. A re-confirm simply appends a fresh RatingSample (its new created_at resets staleness for free — Leitner-like with zero extra state). Cut the EVOI 'leverage by group size' math.

**Settings.** rerate_prompt_enabled (default off until coverage broad) + min-sample threshold.

**Dependencies.** Normalization readiness; session segmentation; item 12 (staleness).

### Tempo variety guard (anti-monotony, no key/harmonic matching)  ·  effort M
**Why.** Repetition-of-FEEL (a long run of ~120 BPM tracks) is a genuine anti-fatigue axis orthogonal to all song/group/sub_group cooldowns. BPM is far more robustly extractable than key, and the explanation ('varied the pace after several ~120 BPM tracks') is honest even under octave errors.

**How.** Additive tempo + tempo_confidence columns, populated by an OPTIONAL extraction script (columns stay NULL and the feature is inert if unrun — no hard librosa dependency). Add a single selection-time multiplier mirroring prev_compressed: a soft penalty when the recent window is monotone in one tempo bucket. Gate the multiplier AND the explanation on tempo_confidence; cap tight (0.7-1.0) so it can never fight a cooldown. DROP the tempo-smoothing/clustering bonus and the harmonic-key half entirely (noisy detection, marginal for gapped playback, poisons explainability when wrong).

**Settings.** tempo_variety_strength + enable; jump-tolerance only if a continuity variant is added later.

**Dependencies.** Optional tempo extraction pass (reuse the existing scan/decode).

### Earworm refractory (one-directional cooldown lengthening)  ·  effort M
**Why.** Catchy songs satiate faster than durable ones; a per-song refractory is a smarter anti-fatigue spacing than a global constant horizon. Safe because it can only ever space a song MORE.

**How.** earworm_horizon = song_horizon * (1 + alpha * earworm_score), strictly >=1.0, so it preserves the anti-repetition floor by construction. earworm_score driven primarily by the normalised inspiration/overall rating (high-rated, catchy). Hard-disabled while cold_start_active so it never starves coverage. DROP the completion-decline satiation detector for v1 — per-song play counts are too small and it double-counts history_multiplier/repeat_credit.

**Settings.** earworm_refractory_strength alpha (default 0 = off).

**Dependencies.** Normalised rating; song_horizon (algorithm.py:234).

### Intent Modes: Focus + Discovery (ephemeral factor lenses)  ·  effort M
**Why.** Lets the user deliberately re-route the SAME factors at generation time without a saved settings blob that drifts. Focus (lead with the per-song 'focus' factor) and Discovery (favour under-played already-rated, under-represented-group songs) are genuinely unreachable via existing settings.

**How.** An ephemeral intent argument to generate_playlist (no DB). Plumb the per-factor normalised multipliers (already computed in normalization.py) onto AlgorithmTrack (additive dict). Focus: swap the lead utility to the 'focus' factor, EB-shrink toward overall when sparse, fall back to overall (and say so) when the factor is missing. Discovery: a temporary per-slot boost to low-repeat-count rated songs in under-served groups (a multiplier you CAN apply per-slot — NOT inverting history_multiplier). Cut Sleep (rests on the volume-contaminated avg_level proxy) and Nostalgia (redundant with a favourites toggle + cooldown relaxation). Decide explicitly that intent modes do NOT disable the cold-start coverage guarantee.

**Settings.** Mode is a request param (ephemeral); optional intent strength.

**Dependencies.** Per-factor normalised multipliers surfaced onto AlgorithmTrack.

### 'Start a station from here' (curated-metadata seed radio)  ·  effort M
**Why.** Everything today is global-pool weighting; a seed-anchored mode is a legitimately new selection entry point the user explicitly logged wanting ('string together similar music'). Built from the user's OWN curated groups/tags, it fits local-first/small-data with zero ML.

**How.** One capped station_multiplier inserted into the score_track chain, decaying linearly to 1.0 over the run so cooldowns/log-weight still bound it. Affinity = Jaccard over shared weight-groups + cooldown-tags + sub_group, plus a fixed same-artist/same-album bonus. DROP the rating-factor cosine (it conflates quality with similarity and is undefined for the unrated majority). Set cold_start_active=False for station runs (exploitation, not coverage). Optional nullable seed_track_id on PlaylistRun (additive, create_all-safe) for resume/why. Every 'why' is a plain shared-tag list.

**Settings.** Single 'Station focus' slider (tight<->loose -> internal cap+decay).

**Dependencies.** None for MVP (metadata exists); optional seed_track_id column.

### Skip-cluster reactive variety pivot (one-directional momentum)  ·  effort M
**Why.** Today a skip penalises one song, not the surrounding strategy — yet a cluster of skips is a strong 'wrong vibe, pivot' signal the system ignores. Reacting to it is genuinely new and low-risk; the symmetric 'hold the groove by loosening cooldowns' half is anti-philosophy and must be cut.

**How.** On regeneration (not per-slot), if the recent tail has >=N low-listened_fraction skips, raise EXPLORATION knobs for the next few slots (cold-start breadth, beta spread, force out of the dominant type cluster). Cooldown floors are a hard invariant the overlay may NEVER lower. Asymmetric and conservative: act only on the skip direction; require a longer streak before damping exploration the other way (or don't). Implemented as a bounded Settings copy at regeneration time. Surface in 'why this song' ('a few skips in a row — widening variety').

**Settings.** reactivity slider + enable (default off).

**Dependencies.** Session boundary; queue-tail regeneration (shared with item 9).

### Type-affinity coherence from shared-song co-membership (the seed idea, safe form)  ·  effort M
**Why.** The user wants weak cross-type coherence ('mood runs') and anti-same-type adjacency. The valuable, deterministic 20% of the affinity-graph lens is buildable now; the learned sequence-EWMA 80% is a feedback-loop trap.

**How.** Derive a static type x type affinity from co-membership of types in HIGHLY-RATED multi-type songs (deterministic, zero new logging, computable on the fly from group memberships + shipped normalised ratings; optional tiny derived cache). Do NOT add a new multiplier — fold the result into the EXISTING group_clustering_bias path (apply_clustering_bias, algorithm.py:152), generalising 'cluster same type' to 'cluster/space affine types' so there is ONE tunable mood-coherence knob and one global cap, and the cooldown floor automatically makes near-distance affinity ~0 (no two-affine-types-adjacent). Require a minimum co-membership sample before an edge influences scoring or appears in 'why'. Cut the sequence co-occurrence EWMA and the directional type-skip matrix; if transition-contrast is wanted, drive it from the DENSE loudness delta instead.

**Settings.** Single 'mood coherence' slider (default 0 = today's behaviour).

**Dependencies.** Group memberships (exist); normalised ratings (shipped).

## Cut (rejected — do not re-propose without new evidence)

- Self-supervised embeddings from rating-factor vectors — category error: ratings are EVALUATIVE not descriptive, so cosine measures 'I judge these equally well', not 'these feel alike'; degenerates to group one-hot for the unrated majority it claims to help.
- MMR diversification as proposed — an empty socket: all its value lives in an embedding that won't be trustworthy at a few hundred songs. Defer a metadata-similarity version inside the station/affinity work.
- Full Thompson sampling (per-slot Gaussian draw) — the baseline is NOT greedy argmax (it's already proportional sampling); a random-feeling, non-reproducible queue is the product's worst nightmare. Replaced by a deterministic UCB / low-evidence boost.
- Session energy-ARC / contour presets (rise-peak-winddown) — borrowed DJ-set trope; the app can't measure session length, the arc resets every batch, and it competes with the actual utility objective.
- Harmonic / key transition matching — noisiest signal in audio DSP, marginal for gapped personal playback, and a wrong key label poisons explainability for a low-confidence gain.
- Attention-budget leaky-bucket integrator — over-engineered for the data (focus ratings sparse, has_lyrics near-constant, novelty term fights cold-start). Reduced to the stateless lyric-dense breather.
- Loudness-dose leaky bucket — an uncalibrated, volume-confounded 0..1 estimate cannot proxy absolute-SPL auditory dose, and it overlaps the existing break-reminder system.
- Completion-decline satiation detector (inside earworm) — per-song play counts are tiny by design, so the trend is noise, and it double-counts history_multiplier/repeat_credit.
- Cross-session same-daypart anti-repetition — misdiagnosed: the event-count song_horizon (algorithm.py:234, max(total_tracks,1)) already delivers multi-day, volume-adaptive cross-session spacing. At most a single optional min-hours wall-clock floor, no daypart buckets.
- Circadian / weekday affinity priors — single-user curated-library effect is modest and heavily confounded by WHEN the user happens to listen; realistic early behaviour is near-neutral or quietly self-reinforcing. Park as a far-later experiment, not roadmap.
- Learned opener/closer scores from session boundaries — circular (they measure the algorithm's own past slot-0 choices) and closer intent is unobservable from a gap. Keep only the session-segmentation primitive plus an explicit strong-start rule.
- Seek-back and volume-up as positive affinity — seek-back isn't instrumented and volume is a single global value, not per-track; mostly noise. Keep only an explicit 'replayed' gesture as a positive input.
- 'More like this' as a group/sub_group BOOST — directly contradicts the anti-same-vibe differentiator; the engine will refuse to deliver the sameness it promises. At most a narrow, bounded sub_group relaxation.
- Per-song skip-position clustering -> auto-trim suggestion — least data-robust part, and the canonical mid-song-bridge case can't be expressed by a single contiguous clip window. Demote to a non-destructive UI hint only, never an auto-utility change.
- Sequence co-occurrence EWMA type edges + directional type x type skip matrix — dominated by the algorithm's own sequencing (feedback loop), cold for many sessions, and smears each weak skip across a fractional-membership outer product. The motivating 'loud-then-delicate' case is a DENSE loudness-contrast problem, solved by a loudness-delta tax instead.
- Plays-since-rating staleness decay — mis-signed: completions are confirmation, not staleness; if anything they should SLOW decay.
- Behaviour-derived provisional RATING routed through rating_multiplier — risks leaking a guessed value into the displayed plain average. Replaced by the two-sided history_multiplier arm, which never touches the rating display.
