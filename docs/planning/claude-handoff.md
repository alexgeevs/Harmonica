# Claude Handoff: Harmonica

This document is for Claude or any future agent joining the Harmonica project. It summarizes the user's intent, the current implementation, and a sensible collaboration split.

## Product Intent

Harmonica is intended to become a serious local-first alternative to YouTube or Spotify for a personal music library.

The core idea is not ordinary shuffle. Harmonica should maximize the user's listening utility while avoiding unwanted repetition. It should understand local media files, curated metadata, ratings, playback history, group-level preferences, cold-start exploration, visual/video assets, and contexts where clustering is either bad or desirable.

The user wants this to become a real app, not only an algorithm demo.

## User Preferences To Preserve

- Keep direction-setting user input in Markdown as it arrives.
- Preserve the current UI colour scheme unless the user asks for a redesign.
- Settings should be real controls: switches, sliders, steppers, selectors, and explanatory text.
- The UI should feel like a serious music app. It should not feel like a thin wrapper around a backend.
- The backend should remain stable and customizable so alternative UIs or agents can plug into it.
- Library sorting/curation will often be done by a separate agent, not manually.
- Metadata import/export should be friendly to external curation agents.
- Downloading/source acquisition is outside Harmonica for now.

## Current Implementation

Backend:

- Python package in `src/harmonica`.
- SQLite app database.
- FastAPI daemon.
- Typer CLI.
- SQLAlchemy models.
- Local media scanner using embedded tags.
- Weighted playlist generator.
- Playback history events.
- Settings persistence.
- Agent-friendly JSON library import/export API.

Frontend:

- React/TypeScript/Vite app in `web/`.
- Current views: queue/player, library, stats, settings.
- Browser audio/video playback.
- Settings controls.
- "Why this song" explanation panel.
- Basic stats view.

Algorithm features already present:

- Logarithmic group weighting.
- Fractional membership across overlapping groups.
- Song/group/subgroup cooldowns.
- Playback-history-aware generation.
- Skip-depth semantics.
- Group rating aggregation.
- Cold-start boost for unrated songs.
- Visual-track priority when generating from the web UI.
- Clustering bias setting for variety versus musical/source run-through behavior.

## Important Product Nuances

Skip semantics:

- Under 10% listened before skip: bad signal, not counted as recently played.
- Under 50% listened: bad signal and partial repeat credit.
- Completed: full repeat credit.

Cold start:

- Startup behavior should not be the same as mature recommendation behavior.
- The user has around 200 songs, each about 5 minutes, so every song needs a fair chance.
- Before more than half the songs have been played twice, every song should have been played or rated at least once.
- Current code has a boost for unrated songs, but it does not yet hard-enforce this rule.

Visual/media behavior:

- Songs may have audio-only and audio-video assets.
- When the UI is active, visual songs should get priority because they are easier to review and rate.
- When the UI is inactive, assume medium songs may not receive attention; the user will mostly rank exceptionally good or bad songs.

Clustering:

- Repetition is often bad, but not always.
- A musical playlist may be better when listened to consecutively.
- The app should eventually support profiles/modes that either suppress or encourage clustering.

Ratings:

- Ratings are 0-5 stars and nullable by factor.
- Default factors: lyrics, music, performance, inspiration, focus, overall.
- Replayability is intentionally not a default factor.
- Group ratings should aggregate from member song ratings and influence groups.
- Future to-do: recency-weighted ratings with session-level outlier detection and regression to the mean.

## Where Claude Can Help Most

The user specifically thinks Claude can help with what a user would actually want from the front end.

High-value front-end/product work:

- Make the app feel like a real music player, not just a generated list.
- Improve now-playing and queue ergonomics: persistent current session, reorder, remove, save, resume.
- Improve library browsing: artist, album, group/source, subgroup/cover-family views.
- Add user-friendly curation flows that can review changes from a curation agent.
- Make stats useful: coverage, repetition distance, skipped/completed trends, overplayed/underplayed groups.
- Turn "why this song" into clear human-language explanations.
- Design profile flows: focus, sleep, entertainment, musical run-through.
- Keep settings calm and usable despite many algorithm controls.

## Suggested Division Of Labor

Codex should usually own:

- Backend architecture.
- Data models and migrations/table compatibility.
- Algorithm correctness.
- API contracts.
- Tests and verification.
- Agent import/export semantics.

Claude should usually own:

- Front-end user flows.
- Layout and interaction design.
- User-facing copy.
- Music-player ergonomics.
- Dashboard and stats presentation.
- Library browsing experience.

Coordinate before editing the same files, especially:

- `web/src/App.tsx`
- `web/src/styles.css`
- `src/harmonica/api.py`
- `src/harmonica/schemas.py`

## Progress (2026-06-25, Claude pass)

Done and on `main`:

- Persistent listening session: a single app-wide audio engine that keeps playing across views,
  a persistent bottom transport bar (seek, time, volume, prev/next), session restored across
  refresh via `localStorage`, reliable progress feeding history.
- Queue management: reorder, remove, jump-to, and saved sessions (list/load/rename/delete).
- Faceted Library browsing (source/artist/theme/variant families) with inline ratings and an
  applicability-aware track editor.
- Human-language "Why this song" derived from the score breakdown, and an Insights dashboard
  (coverage, completion rate, biggest groups, most played).
- Keyboard transport (Space play/pause, Shift+←/→ prev/next).
- Backend (Codex, landed by Claude): saved/named queues API (`GET/PATCH/DELETE /playlist-runs`),
  a real cold-start coverage guarantee (restricts the candidate pool to unplayed+unrated first,
  then blocks third plays until coverage completes), and dub/cover subgroup anti-clustering.
- Dev ergonomics: `scripts/seed_demo_library.py` builds a realistic overlapping demo library
  (browser-playable WAVs); fixed the Vite proxy so `/stats` and `/playback-events` work.

## Current Best Next Step

1. **Video review for visual tracks.** The audio engine is audio-only today; the queue plays the
   audio asset even when a video asset exists. To honor "watch the visual version and rate visuals",
   add a way to play the video asset in a `<video>` surface from now-playing. Best built once the
   real library (with actual video files) lands.
2. **Agent curation review workflow**: export library JSON for a curation agent, import proposed
   changes as a draft, show a diff/review screen of changed groups/subgroups/tags/ratings/assets,
   and accept/reject safely. (Codex to expose dry-run/diff endpoints; Claude to design the review UI.)
3. **Real-library hardening**: scan the user's ~250-song batch, verify codecs/containers are
   browser-playable (transcode policy stays out of the app), and tune cold-start/clustering against
   real overlap and dub families.

