# Harmonica Session Log

A running ledger of the user's direction-setting **inputs** and Claude's **final outputs** (decisions
and deliverables — not intermediate working). Maintained at the user's request (2026-06-27) so the
collaboration is traceable without chat history. Newest entries at the bottom. For the detailed
algorithm rationale see `rating-normalization-and-covers.md`; for verbatim early Q&A see
`user-input-log.md`.

> Reconstructed from memory where it predates this log; treat early entries as faithful summaries
> rather than exact quotes.

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
