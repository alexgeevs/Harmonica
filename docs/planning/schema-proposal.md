# Harmonica Data Schema — Current State, Critique, and Proposal

This document proposes the schema Harmonica should converge on. It is written so any agent
(Claude or Codex) can implement it incrementally without a destructive migration. Persistence
uses SQLAlchemy `create_all` (no migration tool yet), so **adding tables/columns is safe**;
changing or dropping existing columns needs care and a guarded `ALTER`/backfill.

## Current schema (as built)

- `tracks` — song_id, title, artist, album, has_lyrics, sub_group, manual_multiplier,
  clip_start_seconds, clip_end_seconds, audio_only.
- `media_assets` — file_path, asset_type, codec, container, source, source_quality,
  is_lossless, checksum, browser_supported.
- `weight_groups` / `group_memberships(share)` — overlapping weight groups.
- `cooldown_tags` / `track_cooldown_tags`.
- `rating_factors` / `track_ratings(value)`.
- `playlist_runs(name, seed, length, settings_json)` / `playlist_items`.
- `app_settings(key, value_json)`.
- `playback_events(event_type, track_id, media_asset_id, playlist_run_id, queue_position,
  progress_seconds, duration_seconds, created_at)`.

## What's good

The normalized core is sound: tracks ↔ overlapping groups via a join table with fractional
`share`, nullable per-factor ratings, and a flexible key/value settings store. Keep all of this.

## The main inefficiency: history is recomputed from raw events every generation

`summarize_history()` loads **every** `playback_event` and replays them on each queue
generation to derive per-track repeat distance/credit, group/subgroup distances, and cold-start
state. That is `O(total events)` per generate and grows unbounded with listening. The raw event
log is worth keeping for audit, but the hot path should read a small rollup.

### Proposal: a `track_stats` rollup (incremental, O(tracks) reads)

One row per track, updated when a playback event is recorded:

- `track_id` (pk, fk)
- `play_count`, `completed_count`, `skipped_count`, `early_skip_count`
- `last_played_at` (timestamp), `last_event_id`
- `listen_seconds_total`
- `repeat_count` (Harmonica's fractional play credit; powers cold-start "played twice")
- `rating_ewma`, `rating_baseline`, `rating_samples` — recency-weighted rating + a baseline,
  enabling the deferred recency/regression-to-mean work **and** the rating-gated destructive
  trim (compare recent rating to baseline over N plays).
- `loudness_sum`, `loudness_samples`, `peak_level_max` — for average/peak loudness per track.
- `updated_at`

Generation then reads `track_stats` (+ `tracks`/`groups`) instead of all events. `playback_events`
stays as the raw log; it can be pruned or rolled up later. Add an index on
`playback_events(created_at)` regardless.

## Hearing-health additions

Browsers cannot read calibrated SPL (it depends on headphone sensitivity + system volume), so we
store the **measurable** signal and treat dB SPL as a clearly-labelled estimate.

- `playback_events.avg_level`, `.peak_level` — normalized RMS/peak (0..1, dBFS-derived) of the
  audio actually played, from a Web Audio `AnalyserNode`.
- `playback_events.output_gain` — the app's output volume (0..1) at play time.
- Optional `listening_exposure_daily(day, dose, seconds, peak_level)` rollup for fast weekly-dose
  reads (WHO model: 80 dB(A) for 40 h/week = 100% allowance; +3 dB halves the time). Until that
  table exists, compute the 7-day dose from `playback_events` (bounded by a `created_at` index).

Compression is **derived**, not stored redundantly: a track is "compressed" when its preferred
playable asset has `is_lossless = false`. The algorithm and the break-reminder read that.

## Settings (key/value `app_settings`, surfaced as controls)

Additive, all with sensible defaults:

- `compressed_break_reminder` (bool, default **on**) — nudge a short break between lossy songs.
- `loudness_warning_enabled` (bool, default on) + `loudness_warning_level` (0..1 threshold).
- `avoid_consecutive_compressed` (bool, default on) — soft-bias generation away from back-to-back
  lossy tracks when the library has a lossless/lossy mix (a uniform penalty is a no-op when every
  track is compressed, so it never breaks all-lossy libraries).
- `assumed_max_spl_db` (number, optional) — lets a user who knows their gear turn the relative
  estimate into a rough dB figure; defaults conservative.

## Rollout order (safe, additive)

1. Add loudness columns to `playback_events` + health settings (done first; low risk).
2. Add the `avoid_consecutive_compressed` generation bias (gated, soft).
3. Introduce `track_stats` and move `summarize_history` to read it (bigger; coordinate with Codex).
4. Add `listening_exposure_daily` if weekly-dose reads get heavy.

Steps 1–2 are implemented now. Steps 3–4 are the recommended efficiency refactor and are the main
"schema we should use" change; they are additive and can land without disturbing playback.
