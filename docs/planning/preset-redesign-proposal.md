# Harmonica — Preset Redesign Proposal

**Status:** PROPOSAL — pending owner approval. Not wired into the app yet.
**Date:** 2026-07-03. Produced by a background design workflow (map current settings → 3 design
philosophies → synthesis). The old presets (Familiar / Balanced / Discovery / Long game, 2026-06-25)
predate rating-normalisation, satiation/rediscovery, covers/two-level, cold-start, visual-priority,
and clustering knobs, so they silently inherit those behaviours instead of pinning them.

## Why the old presets were stale (the real bugs found)

- **Balanced was a silent no-op** — its 13 values already equalled config defaults, and it pinned
  none of the newer default-on thesis knobs, so its label under-described what the algorithm does.
- **Familiar contradicted itself** — it leaned hard on favourites (high rating ceiling, high
  `group_cooldown_floor`, positive clustering) but set **no satiation**, so a comfort binge literally
  burned songs out — the opposite of "Familiar."
- **Long game ignored the knobs built for it** — it claimed "never wear a song out" using only
  cooldown floors + skip penalty, never touching **satiation** or **rediscovery**.
- **No preset used covers, cold-start tuning, or the audio-only/low-attention context** at all.

## The proposed set (6 presets)

Every preset now **explicitly pins** the satiation trio, rediscovery trio, and the
rating-normalisation family, so each label honestly reflects the full behaviour. All keys are real,
within their min/max and on their step grid, so each applies cleanly today.

### Balanced — *revised* (everyday default; equals "reset to defaults")
```
beta:1.25, group_cooldown_floor:0.05, sub_group_cooldown_floor:0.01,
song_rating_min_multiplier:0.5, song_rating_max_multiplier:2.0, enable_group_rating_multiplier:true,
history_influence_enabled:true, skip_penalty_strength:0.25, cold_start_enabled:true,
cold_start_unrated_boost:2.0, visual_priority_enabled:true, visual_priority_multiplier:1.35,
group_clustering_bias:0.0, satiation_enabled:true, satiation_strength:0.5, satiation_window_days:14,
rediscovery_enabled:true, rediscovery_strength:0.4, rediscovery_halflife_days:60,
rating_normalization_enabled:true, rating_outlier_sd:1.0, rating_session_mood_correction:true,
rating_session_min_songs:10, rating_coverage_ready_fraction:0.6, rating_calibration_enabled:true,
cover_two_level_enabled:false
```

### Familiar — *revised* (comfort listening, protected from burnout)
```
beta:1.5, group_cooldown_floor:0.3, sub_group_cooldown_floor:0.08,
song_rating_min_multiplier:0.6, song_rating_max_multiplier:2.2, enable_group_rating_multiplier:true,
history_influence_enabled:true, skip_penalty_strength:0.15, cold_start_enabled:false,
cold_start_unrated_boost:1.5, visual_priority_enabled:true, visual_priority_multiplier:1.2,
group_clustering_bias:0.35, satiation_enabled:true, satiation_strength:0.4, satiation_window_days:10,
rediscovery_enabled:true, rediscovery_strength:0.4, rediscovery_halflife_days:60,
rating_normalization_enabled:true, rating_outlier_sd:1.0, rating_calibration_enabled:true
```
Fix: satiation stays ON but gentle (0.4 / 10d) so a comfort binge is lightly paced and recovers in
~a week — the comfort loop no longer sours. Ratings ceiling 2.0→2.2; normalisation pinned ON because
this preset leans most on ratings.

### Discovery — *revised* (early days / active-rating; drain the unheard pool)
```
beta:0.85, group_cooldown_floor:0.05, sub_group_cooldown_floor:0.01,
song_rating_min_multiplier:0.7, song_rating_max_multiplier:1.5, enable_group_rating_multiplier:true,
history_influence_enabled:true, skip_penalty_strength:0.15, cold_start_enabled:true,
cold_start_unrated_boost:3.5, visual_priority_enabled:true, visual_priority_multiplier:1.7,
group_clustering_bias:-0.25, rating_normalization_enabled:true, rating_outlier_sd:1.25,
rating_calibration_enabled:true, rating_coverage_ready_fraction:0.4,
satiation_enabled:false, rediscovery_enabled:false
```
Normalisation engages sooner (coverage 0.4) and more tolerantly (outlier_sd 1.25) while ratings are
sparse; skip penalty low (an early skip of a barely-sampled song isn't a verdict). Satiation &
rediscovery OFF — nothing's over-played or dormant yet, and both would drain the unheard pool.

### Long game — *revised* (max variety; never wear a song out)
```
beta:1.0, group_cooldown_floor:0.02, sub_group_cooldown_floor:0.0,
song_rating_min_multiplier:0.5, song_rating_max_multiplier:1.6, enable_group_rating_multiplier:true,
history_influence_enabled:true, skip_penalty_strength:0.4, cold_start_enabled:true,
cold_start_unrated_boost:2.0, visual_priority_enabled:true, visual_priority_multiplier:1.35,
group_clustering_bias:-0.6, satiation_enabled:true, satiation_strength:1.2, satiation_window_days:30,
rediscovery_enabled:true, rediscovery_strength:0.8, rediscovery_halflife_days:30,
rating_normalization_enabled:true, rating_outlier_sd:1.0, rating_calibration_enabled:true
```
The biggest upgrade: strong satiation (1.2 / 30d) + strong short-halflife rediscovery (0.8 / 30d) do
the anti-fatigue work, backed by near-zero cooldown floors and clustering −0.6. Ratings ceiling
flattened to 1.6 so the whole above-threshold library rotates instead of a few favourites.

### Covers — *new* (experimental; explore alternate renditions)
```
cover_two_level_enabled:true, cover_count_log_base:2.5, cover_original_bonus:0.1,
beta:1.0, group_cooldown_floor:0.05, sub_group_cooldown_floor:0.0,
song_rating_min_multiplier:0.5, song_rating_max_multiplier:1.8, enable_group_rating_multiplier:true,
history_influence_enabled:true, skip_penalty_strength:0.2, cold_start_enabled:false,
visual_priority_enabled:true, visual_priority_multiplier:1.35, group_clustering_bias:-0.2,
rating_normalization_enabled:true, rating_calibration_enabled:true
```
The only preset that flips `cover_two_level_enabled:true` (song-first, then rendition). Only does
anything on a library that has real cover/version-family sub-groups. `cover_count_log_base` 2.5 and
`cover_original_bonus` 0.1 are tunable judgment calls.

### Background — *new* (music while you work; audio-only, low attention)
```
beta:1.25, group_cooldown_floor:0.05, sub_group_cooldown_floor:0.01,
song_rating_min_multiplier:0.6, song_rating_max_multiplier:1.9, enable_group_rating_multiplier:true,
history_influence_enabled:true, skip_penalty_strength:0.1, cold_start_enabled:false,
visual_priority_enabled:false, visual_priority_multiplier:1.0, group_clustering_bias:-0.1,
satiation_enabled:true, satiation_strength:0.5, satiation_window_days:14,
rediscovery_enabled:true, rediscovery_strength:0.4, rediscovery_halflife_days:60,
compressed_break_reminder:false
```
Honest stand-in for a "focus" mode: the settings have **no** lyric/instrumental knob, so it can't
select instrumentals — instead it turns **visual priority OFF** (don't spend weight on video you
aren't watching), drops skip penalty (a passive skip isn't dislike), and suppresses the break nudge.

## Owner decisions

1. **Preset count** — 6 delivered (top of the 4–6 range). Covers and Background are the most optional.
   To tighten: cut **Background** first (least mechanically distinct from Balanced), and/or keep
   **Covers** behind an "experimental" label (it depends on the experimental cover flag).
2. **matchPreset breadth** — pinning the full thesis/normalisation stack makes labels *honest* but
   makes a preset "drop its highlight" as soon as you tweak any one pinned knob. Alternative: declare
   only each preset's *defining* keys, so it stays highlighted after small manual tweaks. The workflow
   chose honesty/consistency; both are defensible.
3. **Covers tuning** — lower `cover_original_bonus` to 0.0 to let renditions fully out-compete the
   original; raise `cover_count_log_base` toward 4.0 if cover-rich songs feel over-surfaced.
4. **enable_group_rating_multiplier** — kept `true` everywhere. Flip to `false` in Discovery if
   well-rated sources still crowd out coverage.

## Notes / caveats

- No preset sets any **config-only** key (group-rating bounds, Bradley-Terry cover internals, rating
  internals) — `update_setting_values` would silently drop those. All keys are exposed controls.
- Hearing-health / UI-only knobs (`loudness_*`, `why_show_math`, `default_playlist_length`,
  `avoid_consecutive_compressed`) are deliberately left unset so they don't flip when switching modes
  (sole exception: Background pins `compressed_break_reminder:false`).
- The cold-start **guarantee** ("every song played/rated once before half the library is played
  twice") is still only a *boost/gate* in code — no preset can promise it; that's an algorithm change.
