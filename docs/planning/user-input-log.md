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

