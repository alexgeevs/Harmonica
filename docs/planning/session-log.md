# Harmonica Session Log

A running ledger of the user's direction-setting **inputs** and Claude's **final outputs** (decisions
and deliverables — not intermediate working). Maintained at the user's request (2026-06-27) so the
collaboration is traceable without chat history. Newest entries at the bottom. For the detailed
algorithm rationale see `rating-normalization-and-covers.md`; for verbatim early Q&A see
`user-input-log.md`.

> Reconstructed from memory where it predates this log; treat early entries as faithful summaries
> rather than exact quotes.

---

## Idea attribution ledger

Who originated each design idea, for future reference (the user asked to track this on 2026-06-29).
The dated entries below also tag attribution inline; this is the at-a-glance summary.

**User-originated ideas.** Rating normalisation (accumulate ratings, regress mood outliers toward a
song's mean using a library-wide SD once most songs are rated); cover A/B comparison (flip between
two renditions, say which is better, brief replay to compare); two-level selection (pick song, then
cover); cover count boosts appearance **logarithmically**; the **log base is a tunable setting**;
`overall` = 50% direct + 50% other factors; the original rendition is **slightly favoured by a fixed,
settable, non-decaying nudge**; shared factors shown at song level except a cover-specific
`performance`; displayed rating = plain average (outliers measured against it); per-user rating-scale
calibration (a 4–5-only rater's 4 treated as ~2); weak cross-song type link; the **satiation pattern**
(binge ~2 weeks then burn out) and wanting to avoid quality depreciation from repetition; **after a
song is selected, also use each cover's own individual (hidden) star ratings to pick the rendition.**

**Claude-originated ideas.** The specific normalisation maths (pooled within-series SD yardstick,
winsorising + empirical-Bayes shrinkage + smooth alpha ramp, leave-session-out mood bias); the
satiation **guard** + dormant-favourite **rediscovery** wall-clock multiplier mechanisms; the
"Not now" / "More like this" ephemeral session-steering controls; the optional "show the maths"
explanation view; and — **chosen by Claude (the user explicitly did not know the method)** — using
**Bradley-Terry** to turn the A/B cover verdicts into a single relative `performance` ranking, with a
phantom-average-player Gaussian prior for regularisation and half-credit tie handling.

---

### 2026-06-24/25 — Onboarding & first build
- **User:** Explore the repo; talk to the Codex session; create a `CLAUDE.md` (push frequently to
  `main` under my name); achieve the project vision by end of day; ask clarifying questions first.
  Answers: build a full UI (trust your design judgment); orchestrate Codex then go solo; real ~250-song
  library with heavy overlap/dubs/covers; **commit as alexgeevs only, no Claude trailer**.
- **Claude (final):** Created `CLAUDE.md`, planning docs, and a working thin slice (scanner, SQLite,
  weighted queue, settings, React UI). Established push cadence & attribution.

### 2026-06-25 — Storage, trim, hearing health
- **User:** Gitignore the `Storage/` directory (another agent downloads there). Trim in/out + audio-only
  must be saved per song, durably (survive re-imports). "Conservative" hearing warnings = **more** likely
  to trigger. Build a native Kotlin Android app reading system volume/headphones. NAS on an HDD-in-router?
  Per-device config recoverable by passphrase. Break reminder after **2** consecutive compressed songs,
  pause playback, link the Economist article. Make the DB cross-device compatible.
- **Claude (final):** Per-song trim + audio-only persisted across re-imports; loudness meter + cautious
  warnings + break modal (Economist link); compression-aware algorithm. Phase-1 multi-device backend
  (passphrase-claimable device profiles with per-config song scope). Native Kotlin Android scaffold.
  Answered NAS feasibility: a bare HDD can't run the daemon — needs a small always-on computer (user
  chose old laptop / mini-PC).

### 2026-06-26 — iOS
- **User:** "I'll have the NAS up soon. How do you propose we implement this for iOS? I don't have a Mac."
  Chose: a web app (PWA) for now — "can't be bothered with the developer things," may reconsider with a Mac.
- **Claude (final):** Made the web app an installable iOS/Android home-screen PWA (manifest, Apple meta,
  dependency-free generated icons, prod-only app-shell service worker, safe-area mobile layout). Documented
  the LAN secure-context caveat. Trade-off noted: Safari can't read system volume, so iOS falls back to the
  signal-based loudness meter.

### 2026-06-27 — Remote update
- **User:** Update the git remote to `alexgeevs/Harmonica`.
- **Claude (final):** Repointed `origin`, verified, fixed the one stale URL in docs. Left commit identity
  as `alexgeevs` per CLAUDE.md.

### 2026-06-27 — Codex retired; priorities
- **User:** Codex subscription ran out — stop using it. Work on Phase 2 (web device profiles) **as long as
  network-hosted config isn't compulsory for local use**; install banner — not yet; do the test-DB
  isolation yourself; Android = make it "entirely an iPod" for local music in our UI (phone access soon).
- **Claude (final):** Recorded Codex retirement (now solo-own backend + frontend). Test isolation via temp
  DB (real library no longer polluted). Optional "Device profile" panel in Settings (claim/create, song
  scope, settings snapshot) — local mode stays the untouched default, verified end-to-end. iPod direction
  captured.

### 2026-06-27 — Rating normalisation & cover comparison (algorithm)
- **User:** (1) Normalise ratings: accumulate history; in long sessions, regress ratings >1 SD from the
  average back toward the mean (mood). SD derived library-wide once most songs are rated (most >1×).
  (2) For songs with **≥4 covers**, A/B compare renditions: play two **consecutively** when "active"
  (≥4 of last 5 songs rated), ask during the 2nd which is better, with a brief replay of the prior at the
  same %; bootstrap then revert to stars. Two-level selection (song then cover); cover count boosts
  appearance **logarithmically** (tunable base); `overall` = 50% direct + 50% other factors; original
  rendition slightly favoured; shared factors shown at song level except a cover-specific `performance`.
  Then: switched to **ultracode** — "organise a discussion between several agents… in-depth look at the
  algorithm and the app as a whole. Proceed."
- **Claude (final):** Recorded verbatim decisions. Ran a 22-agent design review (map → design → adversarial
  critique → synthesis); appended an implementation-ready blueprint to the spec doc; it also found two
  pre-existing bugs (additive helpers missing from `init_db`; `variant_counts` ignoring device scope).
  Implemented **Feature 1** end-to-end (Phases A & B): `rating_samples` history + backfill; lazy
  normalisation (pooled within-series SD, winsorise + empirical-Bayes shrink + ramp, session-mood
  correction); `overall` = 50/50; unified song & group ratings. 39 tests green. Flagged 3 deviations from
  the literal request (within-series SD; added shrinkage; default log base 4).

### 2026-06-27 — Multiplier scaling, simple-average display, type links, brainstorm
- **User:** The rating→multiplier should be **continuous** — a well-rated song ~1.5×, only a *maximally*
  rated song 2×, floor ~0.5× (min/max also settable in Settings). The **UI rating is just the plain average**
  of past ratings, and outliers are measured against that average — *not* the internal "magic" value. Add a
  **weak cross-song type link**: a positive rating nudges that type up (long run), while same-type songs may
  be weighted against playing two in a row (e.g. two pop), and songs can have several types. Take inputs
  with a grain of salt; add these and **brainstorm what else** could be added. Keep an md log of every final
  output and every input (this one included).
- **Claude (final):** Created this session log. Confirmed the multiplier already scales continuously
  (4→1.6×, only 5→2× max, floor 0.5× at 0; min/max already settings). Implemented "displayed rating =
  plain average" (fractional stars). Exposed the rating-normalisation settings as real controls. Ran a
  multi-agent **brainstorm + adversarial vetting** workflow (35 ideas) for further enhancements.

### 2026-06-27 — Brainstorm reactions; per-user scale calibration
- **User:** "Not now and More like this are good ideas, write down that you came up with them." Concurs
  with most of the brainstorm preview. New idea: **per-user rating-scale calibration** — if a user tends
  to rate only 4–5, the algorithm should account for that (treat a 4 like ~2, a 4.5 like ~3.5). "Otherwise,
  do continue, these are very good ideas."
- **Claude (final):** **Attribution noted — the "Not now" / "More like this" ephemeral session-steering
  controls were Claude's ideas (surfaced by the multi-agent brainstorm), not the user's.** Implemented the
  user's **rating-scale calibration**: per-factor between-song distribution recentres the user's own
  average to neutral and stretches their used range, so a 4/5-only rater's 4★ song scores 0.75× and their
  5★ scores 1.5× (vs face-value 1.6×/2.0×). Gated on ≥20 rated songs + non-zero spread; tunable via a new
  "Calibrate to your scale" setting. The full brainstorm synthesis (interrupted by a usage limit) is
  re-running; survivors → `algorithm-roadmap.md`. Continuing to Phase C (two-level covers) next.

### 2026-06-27 — Brainstorm roadmap delivered; skip-penalty bug fixed
- **User:** (usage limit reset) "proceed as you were."
- **Claude (final):** Brainstorm synthesis completed → wrote `docs/planning/algorithm-roadmap.md` (19
  vetted items prioritised now/next/later + quick wins + an explicit cut-list). The review's #1 finding
  was a **real bug**, which I verified in code: `history.py` set `skip_penalty = max(...)` over all
  events, so a single early/accidental skip floored a song forever and later completions never recovered
  it; the listened-fraction map was also a coarse 3-bin step. **Fixed:** recency-weighted mean of
  per-event penalties (completions pull it back down; new `skip_penalty_halflife` setting) + a smooth,
  position-sensitive listened-fraction curve. Verified: skip→8 completions recovers to <0.2 penalty; a
  lone skip still scores 1.0. Roadmap confirms the user's type-link idea is mostly already built (endorse
  + expose in "why this song"; reject the learned-graph form) and strongly endorses the simple-average
  display invariant.

### 2026-06-27 — Quick wins chosen; satiation pattern revealed
- **User:** Chose "quick wins, then covers" (other roadmap items still to come later). Revealed the core
  listening pattern: **binge a song ~2 weeks then burn out for months**; the goal is to **avoid quality
  depreciation from repetition** (distinct from rating-age decay). Will **update the algorithm presets**
  once all these factors are in.
- **Claude (final):** Recorded the satiation pattern as a durable preference (memory + roadmap). Built the
  wall-clock layer addressing it: a **satiation guard** (eases off a recently over-played song, recovering
  over a ~2-week window) and **dormant-favourite rediscovery** (resurfaces an above-average song the
  longer it's gone unheard) — both bounded multipliers in the score product, deterministic via an injected
  now-clock, inert until there's play history; exposed as a "Repetition & rediscovery" settings section.
  Also extended **"why this song"** to surface the highest-trust messages it was hiding (you-heard-this-
  recently, eased-off-this-type, resting-it, long-lost-favourite). Fixed a tz bug (SQLite returns naive
  datetimes). 51 tests green. Next: Phase C (two-level covers).

### 2026-06-29 — Optionality + clearer "why this song"
- **User:** The satiation guard must be optional (disableable in settings), and so must the rediscovery
  feature. "Why this song" should be **easier to understand**, with a **longer mathematical explanation
  that can be enabled in settings** (the formula and result). Phase C (two-level covers) should also be
  **optional and off by default**. "Proceed."
- **Claude (final):** Confirmed satiation + rediscovery were *already* optional switches (both
  multipliers early-return 1.0 when their flag is off). Simplified the plain "why this song" reasons —
  dropped the raw ×N.NN multiplier numbers from the prose (e.g. "You rate this highly" instead of
  "(×1.20)"). Added a **"Show the maths in 'why this song'"** setting (boolean, default **off**): when
  on, the panel reveals a collapsible breakdown — group base × every multiplier (manual, rating, skip
  history, new-song, satiation, rediscovery, video, song-rest, version-rest) = final score, with a note
  that score is a relative pick-chance, not a percentage, and neutral 1.00 factors dimmed. Added a
  **`cover_two_level_enabled`** setting (default **off**) plus `cover_count_log_base`/`cover_original_bonus`
  config scaffolding ahead of the Phase C build, surfaced as a "Covers (experimental)" settings section.
  New settings flow through config → settings_store → schema → web types/UI and the run snapshot.
  Added an API test asserting both new toggles default off and are real controls. 52 tests green, ruff
  clean, web build clean. Next: build the Phase C selection logic behind its (default-off) flag.

### 2026-06-29 — Phase C: two-level cover selection (behind default-off flag)
- **User:** (same message) Phase C should be optional and off by default. "Proceed."
- **Claude (final):** Built the two-level selection in a new `covers.py`, gated entirely behind
  `cover_two_level_enabled` (default **off**). When on, the generator groups renditions into *units*
  (a song's `sub_group`; a no-cover song is its own singleton), picks a unit by
  `W(u) = L(n) · SongRatingMult(u) · UnitCooldown(u) · Abar(u)` with `L(n) = 1 + log_base(n_covers)`
  (base 4 → 2 covers ×1.5, 10 covers ×2.66, not ×10), then picks a rendition inside it by its own
  context × within-set preference (`perf_mult` from a directly-rated `performance` star for now;
  Bradley-Terry comes in Phase D) × a small decaying original-rendition prior. `Abar` is a
  *v-weighted average* (not a sum), so cover count only enters via the explicit `L(n)` term — proven
  logarithmic exposure. New `AlgorithmTrack` fields (unit_key, n_covers, song_rating_multiplier,
  perf_mult, is_original_rendition, original_prior_mult) default so the legacy path is untouched.
  **Golden-parity guarantee:** a singleton unit consumes *no* extra RNG draw, so a no-`sub_group`
  library yields a **byte-identical seeded queue** with the flag on vs off — covered by
  `test_golden_parity_*` (ids + scores, incl. under cold start). Also tested: logarithmic exposure
  at a clean state (observed ≈ L(n)/(L(n)+singletons), decisively sublinear), one rendition per slot
  with cover fields in the explanation, and the original-rendition nudge. Frontend "why this song"
  surfaces "one of N versions / the original recording / your favourite rendition" when enabled.
  6 new tests; 58 green; ruff + web build clean. Phase D (A/B comparison + Bradley-Terry) is next.

### 2026-06-29 — Cover refinements + Phase D (Bradley-Terry)
- **User:** The cover log **base should be a selectable setting**. The original nudge should **not
  decay** (but stays a setting). **After a song is selected, the algorithm may also look at each
  cover's individual star ratings (not shown to the user) to pick the rendition.** Do Phase D — but
  "I don't quite know what Bradley-Terry is, I would want an explanation." Later: note in the md that
  **Claude** came up with the BT approach (not the user), and generally track who did what.
- **Claude (final):** (1) Exposed **`cover_count_log_base`** and **`cover_original_bonus`** as real
  settings sliders in the "Covers (experimental)" section; the original nudge is a fixed
  `1 + bonus` (non-decaying). (2) The within-set rendition pick now also multiplies by each cover's
  **own individual rating** (carried in `song_rating_multiplier`, which the unit already averages for
  the song-level frequency, so this adds no frequency bias — only steers WHICH rendition). (3) Built
  **Phase D**: three additive tables (`cover_comparisons` raw verdict log, `cover_rendition_state`
  BT-strength cache, `cover_set_state` lifecycle), a `bt.py` regularised **Bradley-Terry** fit
  (Zermelo/MM iteration, phantom-average-player Gaussian prior so thin/undefeated evidence stays
  finite, half-credit ties, mean-0 log-strengths, order-independent), a `cover_ranking.py` recompute
  service, and `POST /cover-verdicts` (+ `GET /cover-sets/{sub_group}`) that validates the pair,
  appends the verdict, refits, and caches. `perf_mult` now prefers a learned BT strength (bounded
  `exp(γ·strength)` in [0.7, 1.4]) over a manual `performance` star. Added the **idea-attribution
  ledger** above (BT was Claude's choice; the log-base/non-decay-nudge/individual-cover-rating ideas
  were the user's). 8 new tests (BT properties + verdict endpoint + individual-rating pick); 66 green;
  ruff + web build clean. Phase E (the A/B playback UX) is next.

### 2026-06-29 — Phase E: A/B comparison playback UX
- **User:** "Yes, please do proceed." (with Phase E.)
- **Claude (final):** Built the head-to-head comparison experience (all behind two-level covers, so
  inert by default). Backend: `next_pair()` picks the most *informative* pair (closest current
  Bradley-Terry strength × least evidence so far), a `_settle_phase()` that stops prompting once a
  set is well-separated or hits a verdict ceiling, and `GET /cover-comparisons/next` returning the
  two renditions as ready-to-queue items (each flagged with `{comparison: role/peer/set}`; only
  returns a pair when both have playable media + the set is eligible). New config knobs
  (min-covers 4, cooldown 3 songs, min-per-cover 3, max-total 40, active 4-of-5). Frontend: a
  `useCoverComparison` hook detects when the listener is "active" (rated ≥4 of the last 5 songs) and,
  on landing on an eligible cover-set song, fetches the pair and `spliceNext()`s the two renditions
  to play back-to-back; a `ComparisonCard` then appears during the *second* rendition asking "which
  is better?" (first / about the same / this one) with a **replay-the-first** button that plays the
  prior take from the same %-through in a throwaway `<audio>` so the main player + loudness meter are
  untouched. Verdicts POST to the Phase-D endpoint and feed the BT refit. 4 new tests (pair
  eligibility/settle/info-gain + the playable-pair endpoint); 70 green; ruff + web build clean.
  Remaining cover work: Phase F (export/import round-trip of the cover tables) and Phase G (polish:
  surface set "settled/compare-again", readiness, docs).

### 2026-06-29 — Phase F (export/import round-trip) + Phase G (polish & docs)
- **User:** Continue with Phase F (didn't know what it was — asked for an explanation) and Phase G,
  explained once finished.
- **Claude (final):** **Phase F** — the new history now survives library export/import so moving
  devices or restoring a backup keeps your rating history and cover verdicts. `serialization.py`
  exports `rating_samples` + `cover_comparisons` (keyed by `song_id`/`factor_key`, device-local
  `session_id`/`run_id` stripped) and `tracks.is_original_rendition`; on import it remaps by
  `song_id`, dedupes (idempotent re-import), and **recomputes** the Bradley-Terry caches from the
  imported verdicts rather than trusting exported values. **Phase G** — `POST
  /cover-sets/{sub_group}/reopen` ("compare again" for a settled set); a track-editor **cover-set
  status panel** (phase + comparison/version counts + Compare-again) and the **"Original rendition"
  toggle** (the earlier-deferred control); a full feature reference at
  `docs/planning/covers-feature.md`. 3 new tests (round-trip + idempotency + reopen); 73 green; ruff
  + web build clean. The covers feature (C–G) is complete and remains off by default.
