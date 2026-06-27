# Harmonica User Input Log

This file records direction-setting user input, clarification questions, and answers so future agents can understand the intended direction without reconstructing it from chat history.

These notes reflect the user's current intent at the time recorded. They are not permanent constraints: the user explicitly said the direction can change on a whim.

## 2026-06-24: Project Creation

### User Input

The user wants to create a music app named Harmonica. The app should have its own algorithm that aims to maximize the user's utility while avoiding repetition.

The user asked to create a GitHub project named `Harmonica` before providing a prior ChatGPT conversation in Markdown.

### Result

The GitHub repo was created at `https://github.com/alexgeevs/Harmonica`.


## 2026-06-24: Uploaded Algorithm Specification

### User Input

The user added `harmonica_algorithm_spec.md`, based on a previous ChatGPT conversation, and asked to clarify everything, consider what should be done, and plan the whole thing before coding.

### Current Interpretation

The provided spec is the initial algorithmic foundation. It prioritizes a local-first app that generates weighted music queues and avoids repetition at song, group, and subgroup levels.

## 2026-06-24: Clarification Questions And Answers

### First Milestone

Question: What should the first coded milestone be?

Options offered:

- CLI generator
- Web app prototype
- Core library only

Answer: No explicit selection received. The assistant initially carried forward the recommended default of a Python CLI generator, JSON metadata, and a folder scanner, but later answers superseded this toward a full app thin slice.

### Metadata Format

Question: Which metadata format should v1 use as the main editable source?

Options offered:

- JSON
- CSV first
- Both CSV and JSON

Answer: No explicit selection received. The provisional default was JSON, later refined to SQLite plus import/export.

### Library Inventory

Question: How should v1 handle local music files?

Options offered:

- Scan and draft metadata
- Manual metadata only
- No scanner yet

Answer: No explicit selection received. The provisional default was scanning configured folders and creating editable draft metadata.

### Play History

Question: Should v1 persist play history after generating a playlist?

Answer: Generation history only.

User note: Probably this, but everything should be centralized. The main point is the algorithm, but the app would probably be hosted on the local network and not just sort things itself, but also play things.

Current interpretation: In v1, generated queues use virtual history during generation. Exporting a playlist should not automatically assume all songs were actually played. Actual playback history should come from the app player later.

### Playback Target

Question: What should the first playback target be?

Answer: Built-in playback.

User note: The user is thinking built-in playback, but using VLC or the open-source layer below VLC, possibly `ffmpeg`. It will mostly be played and interacted with from the desktop. Phone use should generate a playlist for export when the desktop is unavailable. Do not worry about iOS compatibility yet.

Current interpretation: v1 should include local app playback and playlist export. Browser playback is the first practical implementation path; VLC/mpv integration can be deferred.

### Algorithm Visibility

Question: How much algorithm visibility should v1 expose?

Answer: None of the offered choices exactly.

User note: Debug should be visible in log files. The app should have simple output, but also eventually a richer dashboard. The user wants the app to do most things Spotify can do while still being a web app interacting with a local daemon. Target OS is Windows, but starting with WSL present is acceptable. The architecture is up to the assistant.

Current interpretation: v1 should include JSONL/debug logs and a basic dashboard, while preserving a daemon/client architecture for future extensibility.

### First App Shape

Question: What should the first implementation milestone now be?

Answer: CLI then web.

User note: Not because web is unimportant, but because the web UI should be very customizable. A user should be able to custom-build a UI that plugs into the backend. The backend itself should be customizable, and settings in the UI should reflect that. Settings should not be visible on the main dashboard except through a settings icon. Future playlist modes like focus, sleep, and entertainment may ignore non-fitting songs and prioritize fitting songs.

Current interpretation: Build a backend-first architecture with stable APIs and a replaceable web client. The first coding pass should still aim for a full thin slice.

### Playback Backend

Question: Which playback approach should v1 use?

Answer: Browser audio.

User note: Probably browser audio, but when setting up songs from a playlist, they would be losslessly translated into the target codec.

Current interpretation: Use browser playback for v1. Do not build transcoding yet, but design metadata to support codec and source-quality policy.

### Storage Model

Question: What should v1 use for app data and editable metadata?

Answer: SQLite plus import/export.

User note: Probably, the assistant should decide the architecture.

Current interpretation: Use SQLite as the canonical app store, with JSON import/export for portability and manual editing.

### Playlist Profiles

Question: How should playlist modes like focus, sleep, and entertainment work in v1?

Answer: Default only.

User note: More specific things are a long-run addition.

Current interpretation: v1 has a default generation profile. Named profiles are a future feature.

### Transcoding Scope

Question: How should v1 handle browser-incompatible audio formats?

Answer: Pre-transcode cache.

User note: During initial song download, a separate daemon would make sure files are the same type. For the user personally, download/transcode would be managed by a separate daemon. Others might want something simpler, but that is not a priority.

Current interpretation: Harmonica should not integrate downloader/transcoder logic in v1. It should store codec/source metadata and play local files where possible.

### Network Security

Question: How should the local daemon be exposed?

Answer: Localhost first.

Current interpretation: Bind to `127.0.0.1` by default. LAN access/auth are future concerns.

### Tech Stack

Question: Which stack should be planned around?

Answer: Python plus React.

User note: The user likes and understands Python. They are unsure what React is and think HTML/CSS may work for the UI, but are happy for the assistant to choose React if better. Backend is up to the assistant as long as the algorithm does what the user wants.

Current interpretation: Use Python/FastAPI/Typer for the backend and React/TypeScript for the replaceable web client.

### Metadata Import

Question: How should the scanner create initial track metadata?

Answer: Read audio tags.

User note: Audio tags would over time be adjusted as a vector cloud by looking at how the user reviews songs on factors such as lyrics, music, inspiration, and focus, with more detail and accounting for overlap. Later this can be used either to string together similar music or keep similar music separate depending on settings.

Current interpretation: Use embedded tags when available and store flexible rating/vector fields for later similarity features.

### Codec Policy

Question: What lossless file type should the architecture assume as the preferred normalized target?

Answer: FLAC, with major nuance.

User note: The user provided prior ChatGPT text saying not to normalize everything to FLAC. The user partly disagrees. They want storage-efficient handling that does not add lossy compression beyond what already exists. If it is possible to make files easier to use in the app while reducing storage space, lossless compression is permitted. They think sources are unlikely to be lossless FLAC. If source is FLAC, there can be one FLAC version and another slightly lossy compressed version, not to a noticeable degree, especially over Bluetooth.

Current interpretation: Store source quality honestly. Do not wrap lossy files as fake lossless. Track codec/container/source/lossless fields. Defer actual transcoding policy to later.

### Downloader Scope

Question: Where should downloader/transcoder work sit in the first implementation plan?

Answer: None of the offered options exactly.

User note: Downloader/transcoder should probably be a separate thing. Personally, it would be handled by a separate automated process outside the app. Others might have other plans. It should not be integrated within the app.

Current interpretation: Acquisition is out of scope for Harmonica v1. Harmonica imports local files.

### First Code Scope

Question: What should the very first coding pass after planning deliver?

Answer: Full thin slice.

User note: Try to achieve the full app. Even have a sub-agent make a UI test to plug into the backend. Sub-agents can work in parallel if useful, preferably GPT-5.4 mini rather than GPT-5.5.

Current interpretation: Implement backend, CLI, API, UI, playback, and tests as a thin but connected first version.

### Ratings Scope

Question: How should ratings/vector preferences be handled in v1?

Answer: Manual ratings affect scores.

Current interpretation: Ratings should influence song multipliers in v1.

### Rating Entry

Question: How should v1 let the user enter ratings?

Answer: Simple track editor.

User note: Ratings should be star ratings, minimum 0 and maximum 5, for fields that vary by song. If a song has visuals, there should be an option to see it with visuals and rate visuals as well. If it does not have lyrics, there should be no lyrics rating. Ratings can apply artist-by-artist or group-by-group, aggregated from average ratings in a group. If songs in Meridian are rated 5/5 or 4/5, the group weighting should go up as a group rather than some songs taking more of the group's allocated rating and taking away from other songs.

Current interpretation: v1 implements per-song rating multipliers. Group rating scaffolding should exist but not be active unless later enabled.

### Rating Factors

Question: What should the v1 rating model look like?

Answer: Configurable factors.

Current interpretation: Store rating factors in settings/database rather than hard-coding them completely.

### Rating Influence

Question: How strongly should ratings affect playlist selection in v1?

Answer: Use a broader cap.

User note: 0.5x to 2x for songs, and probably 0.7x to 1.4x for groups, or something like that.

Current interpretation: Map song ratings to a 0.5x to 2x multiplier. Keep group rating cap target 0.7x to 1.4x for later.

### Rating Formula Placement

Question: Where should ratings affect the algorithm in v1?

Answer: Song-first.

User note: When group ratings are "added later", that should mean coded but not implemented yet.

Current interpretation: Implement song rating effects now. Add code/schema scaffolding for group rating effects but leave it disabled.

### Visuals Scope

Question: How should visual/video ratings fit into v1?

Answer: Video playback early.

User note: It should be possible for a song to have both a just-audio file and an audio-and-video file, used context-dependently.

Current interpretation: Support multiple media assets per track, including audio-only and audio-video assets. Browser playback should handle selected asset type.

### Default Rating Factors

Question: Which default rating factors should v1 ship with?

Answer: Audio utility set, with revisions.

User note: Default factors should be lyrics, music, performance, inspiration, focus, overall. Performance applies only to multiples of a song, since many songs in the user's existing playlist are covers of each other. Focus applies only when there are no lyrics. Probably not replayability, because the point is to avoid replay reducing utility.

Current interpretation: Default factors are lyrics, music, performance, inspiration, focus, and overall. Replayability is excluded from v1 defaults.

## 2026-06-24: Documentation And Push Cadence

### User Input

The user asked to make a note of all user inputs in Markdown files, including questions and answers, as the project goes along.

The user wants all inputs saved so future agents understand the direction meant now, while acknowledging the direction can change on a whim.

### Current Interpretation

Maintain this file and `docs/planning/product-direction.md` whenever user direction materially changes.

### User Input

The user asked to push to `main` every time a significant change is made and to assume at least 20 pushes to `main` before v1.

### Current Interpretation

Use small commits and push meaningful increments directly to `main`.

## 2026-06-24: Implementation Authorization

### User Input

The user said: "Implement the plan."

### Current Interpretation

Plan Mode has ended. Begin implementing the full thin slice with frequent pushes.

## 2026-06-24: Settings Direction And Gap Check

### User Input

The user said settings should be more of a switches-and-sliders control surface, rather than the app merely reporting back the values from the original planning answers.

The user said the current work looks good, but looking at it still feels like "this is missing what I want from the final project." They asked what is next and what is still missing.

### Current Interpretation

Settings should become a real tuning interface for the app and algorithm:

- switches for enabling/disabling behavior;
- sliders for algorithm strength, cooldowns, rating influence, and future profile preferences;
- controls that persist settings and immediately affect generation;
- a restrained settings icon entry point from the main dashboard, not a read-only summary page.

The current implementation is a thin slice and foundation, not the final product experience. Future work should close the gap between "working scaffold" and "personal Spotify-like local music system."

## 2026-06-24: Editable Settings, Playback History, And Future Rating Regression

### User Input

The user asked to implement settings now. Settings should be changeable and should explain what each thing means.

The user also asked to save playback history.

The user added a side-note for the future: ratings should eventually weight more recent weightings more heavily, but should also regress to the mean during a listening session. If songs in a session are consistently rated higher than before by more than an outlier-level standard deviation threshold, the app should internally regress those ratings toward the mean. The user explicitly said not to add this yet, only to add it as a later to-do.

The user also said they like the current UI colour scheme and want it kept.

### Current Interpretation

Implement now:

- persistent settings storage;
- settings controls with explanations;
- settings values that affect queue generation;
- playback event history from the web player.
- preserve the existing UI colour scheme.

Do not implement yet:

- recency-weighted rating aggregation;
- session-level rating anomaly detection;
- regression-to-mean correction for unusually high or low session ratings.

## 2026-06-24: History-Aware Generation, Curation Agents, Clustering, And Cold Start

### User Input

The user agreed that the next step should be playback-history-aware generation.

Skip semantics:

- A skip should not always count as recently played.
- If less than 10% of a song was listened to before skipping, it should not count as played recently and can be considered a bad signal.
- Listening to less than 50% is also a bad sign, but should count as about half a listen regarding repeat avoidance, or something similar.

Curation workflow:

- Library sorting/curation will primarily be done by a separate agent created for that purpose, rather than manually.
- Harmonica should support agent-driven metadata workflows cleanly.

Queue quality and clustering:

- Tools like "why this song" and clustering checks are wanted.
- Some things benefit from clustering; for example, a musical playlist can be better when listened to consecutively.
- The algorithm should eventually support modes where clustering is encouraged rather than always suppressed.

Group ratings:

- Group rating aggregation should be added before the next version.

Stats and settings:

- The planned stats dashboard and better settings coverage still sound good.

Cold-start and attention behavior:

- Songs should not be abandoned just because they have not yet been played.
- The user's current playlist is around 200 songs, roughly 5 minutes each, so listening through every song can take the better part of a month.
- The app should prioritize visual songs while the UI is on, because that allows easier access to rankings.
- When the UI is off, assume medium songs will not get attention; the user is more likely to come rank something only if it is exceptionally good or atrociously bad.
- Before more than half the songs have been played twice, every song should have been played at least once.
- During startup, "not having been played" should be defined as not having a ranking.
- Therefore the startup algorithm should not be equivalent to the mature/general algorithm.

### Current Interpretation

Implement next:

- Use playback history in queue generation.
- Classify skip depth into repeat-cooldown and negative-quality signals.
- Add group rating aggregation and apply it to group multipliers.
- Add settings/hooks for clustering mode, history influence, visual priority, and cold-start coverage.

Future direction:

- Metadata should be easy for an external curation agent to write/import.
- Add explicit queue quality tools and "why this song" explanations.
- Add clustering-friendly modes for contexts such as listening through a musical consecutively.
- Build a startup/cold-start algorithm that prioritizes unrated/unheard songs without permanently neglecting songs that have not yet received attention.

## 2026-06-24: Broad Product Pass Expectation

### User Input

The user asked the assistant to do as much as possible before getting back, finish all planned items, and push to main frequently.

The user said the app should be a serious alternative to YouTube or Spotify after this pass.

### Current Interpretation

This next pass should be ambitious and product-oriented, not just a narrow algorithm patch. It should aim to make Harmonica materially closer to a real local music system by adding history-aware generation, skip semantics, group ratings, startup coverage, visual priority, clustering controls, and better UI/API support where feasible.

## 2026-06-25: Claude Collaboration And Front-End Focus

### User Input

The user said to keep all information they have given and what they intend Harmonica to be. The user will direct a Claude agent to this conversation. The assistant and Claude should work together and transfer knowledge to Claude.

The user said both agents can work in parallel today. The shared goal is to make a good final product. The user thinks Claude can help by understanding what a user would actually want regarding the front-end, while this assistant has made a good back-end.

### Current Interpretation

Create and maintain a dedicated handoff document for Claude and future agents. The handoff should explain product intent, current implementation, architectural boundaries, user preferences, and likely division of labor.

Collaboration direction:

- Codex should continue to protect backend architecture, algorithm correctness, data model consistency, tests, and agent-friendly APIs.
- Claude can be especially useful for front-end product thinking, user flows, layout, interaction design, and making Harmonica feel like a polished music app rather than a backend demo.
- Both agents should preserve user direction in Markdown files as it is provided.
- Both agents should coordinate around file ownership to avoid conflicting edits.

## 2026-06-25: Claude Onboarding, Full UI Mandate, And Working Norms

### User Input

The user pointed Claude at the shared Codex session and asked Claude to explore, ask clarifying
questions, create a `CLAUDE.md`, and aim to achieve what the user wants the project to be by the end
of the day.

Clarifying answers from the user:

- **Scope:** The user wants a full, genuinely working UI and trusts Claude's design judgment.
  They have no UI design skills. They found the handoff phrase "persistent listening sessions +
  queue ergonomics" to be opaque jargon; they care about the app feeling and working like a real
  player, not the wording. Claude should decide the design; the user asked whether to consider
  "Claude Design" (DesignSync) — Claude recommended building directly in code to keep it functional
  and preserve the liked colour scheme, offering a visual redesign tool later if wanted.
- **Collaboration:** Claude should orchestrate Codex for backend work for now, then gradually
  transition to doing everything itself. Claude commits and pushes (Codex's sandbox cannot push).
- **Commits:** Author as `alexgeevs` only, with **no `Co-Authored-By: Claude` trailer**.
- **Test data:** The user is supplying a real ~250-song batch from their own playlist (not full
  quality yet). It is a deliberate stress test: musicals,
  artists, overlapping themes, and songs with up to ~5 dubs/covers of themselves across languages.
  Until the files arrive, develop against a synthetic library that mimics that overlap structure.
  The user also thinks the algorithm can be improved to better maximize listening utility.

### Current Interpretation

Claude owns the front-end and will deliver a cohesive, working music-app UI today, preserving the
palette, with frequent small pushes to `main` under the user's name. Backend gaps (persistent
sessions, queue mutation, algorithm improvements) are coordinated with Codex or implemented directly
while keeping models/schemas/tests coherent.

## 2026-06-25: Real Data, Video, Presets, Curation (autonomous build session)

### User Input

The user said: do video review for visual tracks AND broad polish — including simplifying settings
and adding **listening presets**. The presets should be researched and could "steal"/emulate
Spotify-style behaviour through the existing parameters: e.g. a short-run "addictive"/familiar preset,
and a long-term-utility preset that punishes repeats much harder for maximum variety. The user then
left for ~1 hour and said to implement all four of: curation review UI, real-data polish, in-app
curation, and algorithm refinement — "do what you can/want", noting the full 250 songs should be
present.

A separate Storage agent downloaded the real ~250-song batch into `Storage/` (gitignored): one
folder per song with `song_config.json` + media (`.mp4` video and/or `.m4a` audio).

### What was delivered (all on `main`)

- **Real library imported** via `scripts/import_storage_library.py` (250 tracks, 242 with video,
  52 groups). Maps `weight_group_names`→groups, `version_family_name`→sub_group, video/audio assets.
- **Video review**: the player engine became a reparented `<video>` element with native
  fullscreen/scrubbing; visual tracks play in the now-playing stage without breaking cross-view
  playback; tracks still downloading are auto-skipped.
- **Listening presets** (research-grounded): Familiar / Balanced / Discovery / Long game, applied as
  bundles over the existing settings; settings screen grouped into sections.
- **Curation review workflow** (`Curate` tab): export library JSON for an agent, load its proposal,
  see a per-field diff, accept/reject per track, apply via `PATCH /tracks` (+ import for new tracks).
- **In-app curation**: rename/merge weight groups from the Library facet rail.
- **Polish**: Library quick filters (All / Video / Unrated), track counts, connecting state.
- **Algorithm validated on real data**: 0 consecutive same-variant-family pairs (dub families never
  cluster), strong variety, cold-start surfacing all 250 unrated tracks.

### Note for Codex (backend)

`tests/` write to the real app DB (`.harmonica/harmonica.db`) with no isolation, so running the
suite pollutes the working library (added ~6 tracks). Worth adding a temp/in-memory test DB fixture.
Codex was rate-limited (usage cap) during this session, so Claude led the backend-adjacent pieces.

## 2026-06-26: iOS — web app for now

### User Input

"I'll have the NAS up and running sometime soon. For now, how do you propose we implement
this for iOS? I don't currently have access to a mac." After hearing the options, the user
chose: "For now, a web-app is probably best as I can't be bothered with the developer things,
I might reconsider if I get a mac."

### Result

iOS ships as an **installable web app (PWA)**, not a native build — no Mac and no Apple
Developer account required. Made the web app installable to the iPhone home screen: web
manifest (standalone, deep-green theme), Apple touch icon + `apple-mobile-web-app-*` meta,
a prod-only app-shell service worker that never caches the API or `/media`, dependency-free
generated icons (`web/scripts/make_icons.py`), and a hardened mobile layout (safe-area insets,
`100dvh`, icon-only top nav, bottom-docked player). Same install works on Android Chrome.

Trade-off accepted: Safari withholds system volume / output-device from web apps, so iOS
hearing-health uses the in-app signal-based loudness meter rather than the volume×output
estimate the native Kotlin Android client gets. Upgrade path if a Mac later appears: wrap the
same React UI with Capacitor + a small Swift `AVAudioSession` plugin to recover the volume read.
See `docs/planning/multi-device-architecture.md` → "iOS app".
