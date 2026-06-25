# Harmonica Product Direction

This document distills the current direction for future agents. It is intentionally changeable: the user may revise any preference later.

## Product North Star

Harmonica is a local-first music app that aims to maximize the user's listening utility while avoiding repetition.

It should eventually feel like a personal, local, customizable alternative to major streaming apps: library management, playback, queue generation, metadata curation, ratings, and useful statistics, without being locked to Spotify, Apple Music, or any one downloader.

Near-term work should push Harmonica toward being a serious local alternative to YouTube or Spotify, not merely a playlist-generator demo.

## V1 Shape

Build a full thin slice:

- Python backend and algorithm engine.
- SQLite app database.
- CLI for initialization, scanning, queue generation, serving, and import/export.
- FastAPI daemon on `localhost` by default.
- React/TypeScript web UI as a replaceable client.
- Browser playback for local audio/video assets.
- `.m3u8` export for external players or phone transfer.
- Debug logs and explainable score breakdowns.

## Settings Direction

Settings should be a live control surface, not a read-only recap.

The UI should use switches, sliders, steppers, segmented controls, and selectors for algorithm behavior, playback behavior, library behavior, and future profile behavior. These settings should persist and affect queue generation.

The dashboard should stay focused. Settings should remain reachable through a settings icon or secondary view rather than becoming the main surface.

## UI Direction

Preserve the current colour scheme unless the user later asks for a redesign.

Claude may help with front-end product thinking. The current priority for the UI is to turn Harmonica from a technically capable local app into something that feels natural for a real listener: good queue ergonomics, visible feedback, rich but calm library browsing, explainable recommendations, and settings that feel like controls rather than documentation.

## What Matters Most

- The algorithm is central.
- Larger groups should get more weight, but sublinearly.
- Songs should stay eligible rather than being removed from the pool.
- Recent songs, groups, and variants should recover gradually through cooldowns.
- Playback history should affect future queues, but skips should be interpreted by how much of the track was heard.
- Cold-start behavior should prioritize unrated/unheard songs and must differ from the mature recommendation algorithm.
- Overlapping weight groups should not cause unfair double-counting.
- Covers, reprises, live versions, and variants should be controlled with subgroups.
- Ratings should affect utility, but should not destroy anti-repetition behavior.
- Some contexts benefit from clustering, such as listening through a musical consecutively, so future profiles should be able to encourage or suppress clustering.
- The backend should be stable and customizable so other UIs can plug into it.
- Metadata workflows should be friendly to external curation agents, not only manual editing.

## V1 Algorithm Defaults

- `beta`: `1.25`
- Song recovery horizon: total number of tracks in the library.
- Group recovery horizon: `min(number_of_weight_groups, 12)`.
- Group cooldown floor: `0.05`.
- Subgroup recovery horizon: `min(30, total number of tracks)`.
- Subgroup cooldown floor: `0.01`.
- Default group multiplier: `1.0`.
- Default song multiplier: `1.0`.

## Ratings Direction

Ratings are 0-5 stars and nullable per factor.

Default rating factors:

- lyrics
- music
- performance
- inspiration
- focus
- overall

Important applicability rules:

- If a track has no lyrics, lyrics should be non-applicable.
- Focus applies mainly to tracks without lyrics.
- Performance applies mainly where there are variants/covers of the same song.
- Replayability should not be a default factor because repetition already lowers utility.

V1 scoring:

- Song ratings affect song multipliers now.
- A 0-star effective rating maps to about `0.5x`.
- A neutral 2.5-star effective rating maps to about `1.0x`.
- A 5-star effective rating maps to about `2.0x`.

Future scoring:

- Group ratings should aggregate from track ratings and influence groups, likely capped around `0.7x` to `1.4x`.
- This should be coded as scaffolding but not enabled in v1 scoring.
- Rating aggregation should eventually weight recent ratings more heavily, but detect session-level rating drift and regress toward the mean when a session looks like an outlier. This is a future to-do, not a current feature.

## History And Cold Start Direction

Playback events should feed back into queue generation.

Skip interpretation:

- Less than 10% listened: do not treat as recently played; treat as a negative signal.
- Less than 50% listened: treat as a bad sign and roughly a partial listen for repeat avoidance.
- Completed tracks should count fully for repeat avoidance.

Cold-start behavior is separate from mature behavior:

- During startup, unrated songs need deliberate coverage.
- Before more than half the library has been played twice, every song should have been played or rated at least once.
- In startup mode, "unplayed" can be approximated as "unrated."
- When the UI is active, visual songs can be prioritized because they are easier to review and rank.
- When the UI is inactive, assume only unusually good or bad songs will get active ratings.

## Media And Codec Direction

Harmonica imports local media files. Downloading and source acquisition are outside the Harmonica app.

The app should store source and codec truth clearly:

- file path
- codec
- container
- source
- source quality
- whether the source is lossless
- checksum
- whether the asset is browser-supported

The app should not pretend lossy sources have become lossless simply because they were wrapped in a lossless container.

Transcoding is not a v1 feature. Future tooling may keep storage-efficient versions and, where useful, separate playback-optimized assets.

## Deferred Ideas

- Downloader/source-acquisition daemon.
- Transcoding/cache pipeline.
- LAN access and authentication.
- Focus/sleep/entertainment playlist profiles.
- Full switches-and-sliders settings editor with persistent algorithm tuning.
- Recency-weighted rating aggregation with session outlier detection and regression to the mean.
- Explicit agent-friendly metadata import/export workflows.
- Clustering-friendly playlist modes, including musical/source run-through behavior.
- Rich statistics dashboard.
- Similarity/vector cloud based on ratings and metadata.
- Native iOS app or deeper phone integration.
- VLC/mpv/libVLC backend integration.

## Working Norms

Push directly to `main` after significant increments.

Keep direction-setting user input in Markdown planning docs so future agents understand the user's intent without relying on chat history.

When working with another agent such as Claude, coordinate by subsystem and file ownership. Prefer letting Codex own backend/data/algorithm/test changes and letting Claude focus on front-end user experience, unless the user gives different instructions.
