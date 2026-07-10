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

A separate Storage agent placed the real ~250-song batch into `Storage/` (gitignored): one
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

## 2026-06-27: Codex retired; priorities; Android = "an iPod"

### User Input

- **Codex is retired** — the user's Codex subscription ran out, so Claude now solo-owns the whole
  codebase (front-end *and* backend). Do not resume the old Codex session.
- On the four open threads: (1) **build Phase 2** (device profiles in the web app) — *"as long as
  the files for a network-hosted thing aren't compulsory for a local-hosted thing"* (i.e. configs
  must stay optional; local-only use must keep working with zero config). (2) Install-hint banner:
  *"probably not just yet."* (3) Test-DB isolation: *"Do this yourself."* (4) Android: *"Sounds
  good, I will give you access to the Android phone shortly, basically you should make it entirely
  an iPod or something like that where its sole purpose will be to play local music in your UI."*

### Result

- Recorded Codex retirement in `CLAUDE.md` and memory; Claude owns backend going forward.
- **#3 done:** `tests/conftest.py` redirects `HARMONICA_HOME` to a temp dir so the suite can no
  longer pollute the real ~250-song library (verified: 250 → 250 after a full run).
- **#1 done:** optional "Device profile" panel in Settings (claim/create, song-scope picker,
  settings snapshot); active profile scopes Library + queue; local mode stays the untouched
  default (verified end-to-end). See `multi-device-architecture.md` → Phase 2.
- **#4 framing captured:** the Android client is to be a dedicated **"iPod"** — a single-purpose
  local-music player driven by Harmonica's algorithm, syncing its songs/config from the daemon and
  playing offline from a phone folder. Build resumes once the user grants phone access.

## 2026-06-27: Rating normalisation & cover comparison (algorithm direction)

### User Input

The user set two algorithm directions and asked them recorded as evidence (verbatim Q&A is in
`docs/planning/rating-normalization-and-covers.md`):
1. **Rating normalisation** — accumulate rating history; strip mood noise. The standard deviation is
   **library-wide, per factor, derived once the majority of songs are rated** (most ideally >1×), used as
   the yardstick to regress a song's outlier rating (>~1 SD from that song's own mean) toward the mean.
   Plus session-mood correction for sessions of >10 rated songs.
2. **Cover comparison** — songs with **≥4 covers** (same `sub_group`) get **consecutive-playback A/B**
   (play cover A, then B; during B ask "which was better?", with a brief "replay A at ~same %"), only when
   **active** (≥4 of last 5 songs rated); bootstrap then **revert to stars**. **Two-level selection**: pick
   a song from shared ratings, then a cover from cover-specific **performance**; cover count boosts
   appearance **logarithmically** (tunable base); `overall` = 50% direct + 50% mean of other factors;
   original rendition gets a small prior.

The user then switched the session to **ultracode** and asked for a multi-agent design review of the
algorithm and the app as a whole before/while implementing.

### Result

Captured decisions in `rating-normalization-and-covers.md` (incl. verbatim Q&A). Launched a four-phase
multi-agent design review (map → design → adversarial critique → synthesis) to lock the detailed math and
schema before implementing. Implementation proceeds from the synthesised blueprint.

## 2026-06-30: Multi-user model, NAS deployment & security posture

### User Input

While reviewing a code-slim + security pass, the user set product/deployment direction:
1. **Deployment:** the daemon will run **inside a Docker container on the NAS** (so the container is
   the effective filesystem/network boundary).
2. **Multi-user model:** if two users overlap in the music they pick, the **same source file should
   be reusable for both** (de-duplicated media), **but** a user must **not** be able to see what
   other users listen to from the UI or anywhere else (listening privacy between users).
3. **Current data is placeholder:** media lives under `Storage/` in the Harmonica dir for now, the
   playlist is a placeholder, and the **attributions aren't fully set up correctly** yet.
4. Asked to fix the **very bad** security issues, keep changes small, then assess if the project is
   ready.

### Result

Fixed the one **critical** finding (arbitrary local file read via `/media`) plus the compounding
medium ones, all backend-only, UI untouched: a `path_within_root` guard confines media serving,
`/scan`, and the scan walk to `settings.effective_media_root` (defaults to `Storage/`; set
`HARMONICA_MEDIA_ROOT` to the mounted volume in Docker), and imported numerics are sanitised.
The **multi-user privacy** requirement is **recorded but not yet enforced**: there is no API auth
beyond the per-config passphrase and listening data is not scoped per user. That — plus correcting
the placeholder attributions — is on the list for the "is it ready?" review before any multi-user or
off-localhost exposure.

## 2026-07-02: Settings UX polish + algorithm-personalisation scope decision

### User Input

After a live look at the running app (250-song local library), the user was "very pleased with the
UI" and asked for a batch of Settings fixes:
1. **Toggle switches should visibly move.** The on/off switches only changed colour/label; the knob
   should slide position when flipped so it reads as a real switch.
2. **"Covers" shouldn't be labelled experimental.** Questioned why the covers section is marked
   experimental.
3. **Settings must be apply-on-click, not live.** The control previously read "Saved" as soon as
   anything changed; the user wants an **Apply button while there's a pending difference**, turning
   into a **"Saved" status element once applied** (nothing takes effect until Apply is pressed).
4. **Reword the sidebar footer** ("play what you love without wearing it out") — didn't like it.

Also a **scope decision**: the user considered having the *algorithm itself* adapt to the user's
utility function, thought it through, and concluded it isn't feasible — so **that is explicitly NOT
a feature we will build.** The existing utility-maximising weighting stays as-is.

### Result

Front-end only. Switches rebuilt as a sliding track+knob (accent track when on, animated knob
travel, `role="switch"`/`aria-checked`); the covers section renamed "Covers" with a plain-language
note (still off by default); the Settings side panel now shows **"Apply changes"** while the draft
differs and a non-interactive **"Saved"** status chip once clean, and **presets now stage into the
draft instead of auto-applying** (consistent with apply-on-click); sidebar footer reworded to
"Your library, sequenced by what you'll love hearing next — not random shuffle." Build + typecheck
clean; daemon serves the new bundle live.

## 2026-07-02: Classification architecture discussion (song grouping / Venn / hidden groups) — IN PROGRESS

This entry records an ongoing design discussion (no code written yet). The user asked for a full
record of every one of their inputs and how the back-and-forth evolved. Chronological:

### Input 1 — the ask, and the motivating reflection

- **Reflection (verbatim intent):** the user "likes this project a lot" and would use it, but their
  own appetite for music has faded — they suspect from having "listened to the best songs over and
  over until there was no novelty and started getting no utility." Poetic that the app meant to solve
  exactly that is finished only now. Not a problem; they expect to return and will keep building it
  regardless. *(This is the app's founding thesis — repetition-driven utility decay — stated as
  lived experience. Worth preserving.)*
- **The request:** knowing the architecture and how the algorithm works, **Claude should write the
  Markdown prompt file for how a classification agent should classify songs** — by **researching each
  song online** (the user doubts multimodal models can "listen" yet, so research-based, not audio),
  **not by listening** — **and how to "draw the Venn Diagrams."**
- **The trigger:** looking through the local library, "Opportunity Rover" has **14 songs** when only
  **1** is actually about the Opportunity Rover. A section shouldn't have been created just for that
  one song, and the original import agent "just threw in a bunch more songs in addition."
- **Process the user set:** (1) **first discuss** solutions; (2) then Claude writes the classification
  **prompt MD**; (3) then how to **import** the classification into the app once done; (4) then how to
  **verify** the import succeeded.

### Input 2 — "explain how the algorithm deals with overlap"

Interrupted a multiple-choice question to ask this directly. Answer given: overlap is handled by
**fractional membership** (`q = 1/k`, a song in k groups splits its weight, never multiplies) plus
**per-group log-weight divided by group size** (`m_g(1+β ln N_g)/N_g`), with **group cooldown applied
inside each group's term** so a recently-played group damps only that one term of an overlapping song.

### Input 3 — "I don't know what the venn diagrams mean… some songs have 3 or 4 tags"

The user clarified they had no specific "Venn diagram" feature in mind — the phrase was their instinct
reacting to songs carrying **3–4 weight groups**. Established: **some overlap (2 groups) is correct and
intended; 3–4 is a warning sign** (dilution via `1/k`, and the 3rd/4th slot is where junk hides). The
"Venn diagram" was reframed as a **QA/review artifact** the classification agent emits (groups, sizes,
overlaps, auto-flagged smells) so the user can approve a classification **before** import.

### Input 4 — the core grouping-model decisions

- **Weight-group budget:** a song may have **up to 2** weight groups from {topic, theme, mood}, **plus
  `artist` which is always its own group, present on every song** (including standalones) and assumed
  reliable ("can't go wrong").
- **Small-numbers stage is the open worry:** large groups behave well; what about small ones? The user
  reasoned that a song that is the **sole song by its artist** but also in another group should play a
  bit more (its artist-half is full-strength while the other half is standard) — and said **"that
  sounds good."** *(Confirmed correct against the formula: the sole-artist song gets a full `1.0`
  per-song share from that half.)*
- **Meridian vs Marlowe Vance (near-coextensive groups):** the user suspected almost every
  Meridian song is also LMM and asked whether to simplify/merge such cases. Concluded **leave it be** —
  merging only helps the perfectly-overlapping case and adds complexity for the one stray song. Agreed.
- **Sub-groups OFF by default** — they are for **covers**: a cover **shares the general weight groups of
  the original song** and is additionally marked a cover (so it's **less prominent**).
- **On Claude's proposed shape:** (1) classification prompt — **yes**; it should note the agent **may
  create a group** when a song genuinely fits with another song *and no group for that overlap exists*,
  and should clarify the agent **may leave a song with only its artist group**. (2) Review artifact —
  **"possibly, why not."** (3) import + (4) verify — **"sounds good… this is the backend so your
  responsibility."**
- **New question (Minecraft):** "if I have 1 song about minecraft in a library of songs not about
  minecraft, I would want it to have the classification. What do you think?" → **Answer: yes, tag it.**
  Key insight established: **the sin in Opportunity Rover was that the label was FALSE for 13 songs, not
  that the group was small.** A *truthful* singleton group is nearly free (base stays ~1.0, no
  coupling) and future-proofs. **Rule: every membership must be true of the song; there is no group-size
  floor.**
- **Process:** **don't implement yet** — still discussing. **"Possibly call a workflow to figure out
  what is best (not for the agent prompt, but the group/sub-group architecture), including outside
  research if relevant. Then let's discuss this again shortly."** → A background research **workflow**
  was launched (5 parallel investigators — small-N math audit, outside diversity research, taxonomy
  hygiene, cover architecture, edge-rulebook — → 1 synthesis). Research only, no code.

### Input 5 — Opportunity Rover was a duplicate, and the hidden-group idea

- The user noted the group **"Space" has the same 14 entries**, so it's identical to "Opportunity
  Rover"; the songs **do** fit "Space" well, so **Space is legitimate** and the agent just
  **accidentally duplicated** "Opportunity Rover." *(Confirmed: `"Opportunity Rover / Space"` is one
  compound label the old Storage importer split on `/` into two identical groups. Fix = drop the
  duplicate, keep Space. The structured `import-json` path has no delimiter-splitting, so this bug
  class disappears.)* The lone-Opportunity-Rover song **should not be its own group** — it fits Space.
- **The hidden-group decision (new architecture element):** the user concurs the singleton novelty
  boost is good, but was thinking **UI-wise**. Split: a singleton on a topic like **Minecraft** (could
  realistically grow) is fine to show; **Opportunity Rover** (unlikely to ever grow) should get the
  **novelty→utility boost but NOT be shown to the user**. Rule the user stated: for a singleton group
  the agent should ask **"Could more songs in future appear in this group?"** — if **no** (even now),
  the group can be **hidden** — visible on the backend / in the song's own metadata (when clicked), but
  **not in the library list** or group-browsing surfaces.
- **Agreed design:** add an **additive `WeightGroup.hidden: bool` (default false)** flag. It is
  **UI-only** — the algorithm ignores it entirely, so the novelty boost is preserved; only library
  browse / group lists filter `hidden = false`; the song-detail view still shows hidden groups. Yields
  a **three-tier vocabulary**: *visible weight group* (scores + browsable: artist, growable
  themes/moods), *hidden weight group* (scores + not browsable: true one-offs), *cooldown tag* (no
  long-run score, short-run variety only). Guard: hidden groups still count against the ≤2 topic budget.
  Open sub-question deferred to round two: when a growable theme (Space) and a one-off both apply, drop
  the one-off as redundant, or keep it hidden for metadata? (Claude leans **drop**.)

### Input 6 — two side-notes

1. **Presets are probably out of date and will be modified shortly.** If the research agents report
   based on the current **defaults/presets** (Familiar / Balanced / Discovery / Long game), treat those
   values as **provisional** — the numbers will likely change soon, so don't anchor the architecture on
   them.
2. Asked for **this record** — every user input this conversation and how the back-and-forth went.

### Input 7 — round-two decisions (after the research workflow reported)

The workflow's headline: the algorithm's math is **sound and needs no structural change**; the
Opportunity Rover failure was purely a **truth-of-membership** failure (fix = per-song truth test +
canonical-name registry, **no size floor**). Real-library measurement: 250 tracks, 93 artists, **83
of 93 artists have ≤3 songs** (so the "accurate tagging buys airtime" boost is ≤~13% here). The
user's round-two calls:

- **Mood → cooldown tag by default (agreed).** The user concurred with the recommendation that a
  broad mood should ride the short-run cooldown-tag axis, not spend an aboutness weight-group slot;
  a mood becomes a weight group only if the owner deliberately curates it as a preference bucket.
- **Frequency-neutral guard stays available (user pushback).** "Just because it's a non-issue here
  doesn't mean it is elsewhere." So the optional frequency-neutral anchor (adding a truthful lonely
  tag neither boosts nor dilutes) must exist behind a setting — inert in this library, but there for
  a library where one artist has many songs. Don't design as if small artist groups are guaranteed.
- **Multi-artist = Option C (agreed).** Songs with 2–3 genuine performers (collaborations, not just
  covers) each get their own artist weight group **but share a single artist "slice"**, so the song's
  total weight is invariant to the number of credited artists (no +8% inflation for having more
  names) while every collaborator still accrues fair long-run credit. Uses the existing
  `GroupMembership.share` field with deterministic shares (1/N of the artist slice). The **artist
  axis is separate from the ≤2 aboutness budget** — collaborations expand the artist axis, never
  spend a topic/theme slot. A trivial "feat." mention with no real performance may stay a cooldown
  tag instead.
- **Cooldown tags can be NEGATIVE (new decision).** Tags should support **affinity**, not only
  repulsion — e.g. two consecutive musical numbers that "go better together" should be *encouraged*
  to cluster, not spaced apart. This is the concrete mechanism for the long-standing intent
  ("a musical playlist can be better listened to consecutively"; clustering-encouraged modes). A
  cooldown tag gains a **signed strength** (positive = space apart, negative = pull together).
  Forward-looking extension the user raised: the algorithm could **learn** affinity — if a song
  consistently earns a higher rating when it *follows* another specific song, that pairing is a
  candidate for a learned negative-cooldown/affinity link. (Learned pairwise affinity = future; the
  signed-tag mechanism is designed now.)

### Result / consolidated design

Wrote the agreed architecture to **`docs/planning/classification-architecture.md`** (three-axis
model, truth test, three-tier vocabulary incl. `hidden` groups, Option-C artists, signed cooldown
tags, cover/sub-group rework, additive-only schema, review "Venn" artifact, import + verification
plan, and the still-open questions). Presented to the user for approval before the classification
**prompt MD** is written and before any code.

### Input 8 — proceed with deliverables; build presets in parallel

The user approved moving from discussion to artifacts: (a) **write the classification prompt** (done),
then (b) **build the import + verification guide now**, and (c) **spin up sub-agents specialised in
the algorithm presets to design new targeted presets**, since the algorithm has changed since the
presets were last built (2026-06-25) — they run **in parallel** with the main work. Also refined:
the **~2 aboutness cap is a soft guideline, not a hard limit** — if a big topic and a small/niche
topic both truthfully fit, keep both (a truthful distinctive tag is never dropped just to stay under
the cap).

### Deliverables produced (all on `main`)

- **`docs/agents/song-classification-prompt.md`** — the classification agent prompt: truth test,
  ordered procedure (research → cover check → Option-C artists → aboutness → cooldown tags →
  confidence/review), naming/reuse, import-ready payload (extensions as ignored-today keys), the
  review "Venn" map, DO/DON'T + self-check.
- **`docs/agents/classification-import-and-verify.md`** — the import + verification guide. Documents
  the key gotcha that `import-json` only ADDS memberships (can't remove a song from a bad group), so
  removal needs a clear-then-import pass.
- **`scripts/verify_classification.py`** — read-only audit (over-broad groups >25%, over-tagged
  songs, artist-share sums ≈0.5, sub_group family validity, optional DB-vs-payload cross-check). Ran
  it on the current placeholder DB: **289 flags** (3 groups at 30% each, songs with up to 8 groups,
  224 singleton sub_groups) — i.e. it correctly pins exactly what the reclassification will fix.
- **`scripts/reclassify_from_payload.py`** — the corrective clear-then-import helper (backs up the DB,
  clears groups/tags/sub_group for the payload's tracks, applies via the canonical importer, prunes
  emptied groups). This is the deferred one-off corrective pass (§12.4) — provided but not run.
- **Preset redesign workflow** launched in the background (map current settings → 3 design
  philosophies → synthesis) to propose new targeted presets against the *current* knobs.

### Status

Design **approved**; the three requested artifacts (classification prompt, import guide, verification)
are **built and pushed**. No algorithm/schema changes made (deferred by the user). The extension
fields (`hidden`, signed cooldown strength, membership `reason`) are captured in the payload but not
yet persisted — they wait on the deferred additive-schema work. Preset-redesign sub-agents running;
results to be reviewed with the user next.

## 2026-07-03: Public website

- **Website (harmonica.org.uk):** the user asked for a public-facing site — small enough to host on
  GitHub, no cookies, nothing unnecessary; an MD file agents read instead of the HTML (`llms.txt`);
  clear download links (repo + releases for Android / PC web / NAS, none published yet); legal
  disclaimers (as-is, open-source, "best set up with an AI agent — doing it by hand is tedious",
  self-hosted, playing a library the user already keeps); the app's colour scheme; footer
  contact `contact@harmonica.org.uk`. Three authors (Fable, Sonnet 5, Opus 4.8) each produced a
  simple and an embedded-preview variant.
- **Decisions:** site lives in `site/` in this repo (reversible); licence decision **held**
  (MIT vs Apache-2.0, attribution matters to the user); preview/mock variants rejected ("placeholder
  vocabulary abominable" — flagged a possible future *UI vocabulary audit*); **Fable simple** picked
  as `site/index.html`, Opus simple kept as runner-up; "bubbles" (rounded cards/pills) removed in
  favour of flat divider lists.
- **Analytics side-note:** GitHub Pages lacks visit analytics; the user wants cookie-free, ideally
  server-side stats (options discussed: self-host + GoAccess, Cloudflare in front, GoatCounter).
  Explicitly must not affect the site's design.
- **Git identity:** commits are authored as `alexgeevs <contact@harmonica.org.uk>`.

## 2026-07-09: Copy-review feedback + feature requests from the edit pass

The user edited `docs/planning/copy-website.md` / `copy-app.md` and returned them with inline
notes. Beyond wording, the notes carry product direction:

- **Settings explainability:** anti-repetition/variety controls should each explain which algorithm
  variable they change, offer a view of the modified full algorithm, and show worked examples
  (a 10-song vs a 100-song library, ceteris paribus).
- **Preset persistence semantics:** editing Custom then switching presets must keep the custom mix
  saved (per user); editing a named preset saves the change *to that preset* rather than flipping to
  Custom; reset-to-default available per preset and for all settings.
- **Scale-free parameters:** algorithm settings should operate on a % of the library, not absolute
  song counts, so behaviour generalises beyond the ~250-song default tuning.
- **Rating semantics:** a single listen must never be double-counted by repeat taps. (Code already
  ignores same-value re-taps; an immediate correction, e.g. 4→5, currently appends both samples to
  the running average — candidate refinement: same-session correction replaces the last sample.)
- **Public ratings option:** per-user profiles should later offer making one's ratings visible to
  the household. Not implemented; must not be advertised on the site until it exists.
- **Official embedded players (idea):** optionally embed the YouTube/Spotify official players in the
  app where their terms allow, as an alternative to local files.
- **llms.txt:** should describe the agent-facing settings interface (`GET`/`PATCH /settings` JSON
  API) — there is no config file; agent setup-flow wording must describe importing the user's
  existing files only.
- **CurateView honesty:** "nothing is written until you apply" is imprecise (the proposal JSON does
  exist on disk); the user flagged such inconsistencies as a reputational risk given prompt-injection
  concerns. Wording must say nothing *in the library* changes until apply.
- **Agent setup docs:** provide agent-neutral setup docs (README/AGENTS.md) so the project does not
  depend on a Claude-specific working guide.

## 2026-07-09 (later): Decisions from the copy review, applied

- **Punctuation register (binding):** full stops instead of semicolons everywhere in user-facing
  copy ("I just don't like semi-colons. I also despise em-dashes."). No exclamation marks. The
  owner capitalises words more than usual; keep their capitalisation (e.g. "Open-Source").
- **Rating semantics changed in code, not in copy:** a re-rate within 15 minutes now revises the
  last sample in place (`RATING_CORRECTION_WINDOW`); only a later rating appends to the running
  average. One listen can never count twice.
- **New profiles from scratch:** the create-profile form gained a "Start from default settings"
  checkbox; otherwise the profile still snapshots the current settings.
- Profile wording: "universal settings" rather than "shared settings"; empty-library banner
  explains household de-duplication in plain words.
- **Embedded official players (YouTube/Spotify):** approved as an optional feature, never the
  default.
- **Shared ratings on a NAS** for overlapping songs: approved as a future feature; not advertised
  until built.
- **Config file consideration:** settings currently live in the SQLite DB under `.harmonica/`
  (now stated in llms.txt); a deployment-level config file remains a consideration.
- **New docs:** `AGENTS.md` (provider-neutral agent entry point), `CONTRIBUTING.md` (bugs via
  issues, fixes via PR), `docs/agents/api-and-custom-ui.md` (endpoint map + plugging in a custom
  UI via `HARMONICA_WEB_DIST`), `docs/agents/algorithm-and-song-fields.md` (algorithm summary →
  what each song_config.json field should be based on). README points at the first two.
- **llms.txt restructured:** source + run instructions, the real five-step agent flow, settings
  API + SQLite location, Discovery advice.
- **Contact mailbox:** the `contact@harmonica.org.uk` mailbox backs the footer contact line.

## 2026-07-09 (evening): Docs and copy refinements

- **Rating hint** reduced to "Stars show your running average." — the correction behaviour needs
  no narration. Reset-to-defaults button design confirmed.
- **AGENTS.md** is the tracked agent guide: it is the cross-vendor open standard for
  agent instructions (adopted well beyond any one provider), so it is the impartial choice and is
  auto-discovered by most coding agents.
- **README** now links the website up top and states the licence at the bottom. The runner-up
  site candidate was deleted. llms.txt gained a NAS-transfer line (mount the share or copy with
  SMB/rsync/Syncthing before importing).
- **Planning docs as a showcase:** the owner wants the strategy and back-and-forth visible as a
  demonstration of directing AI-assisted development end to end.

## 2026-07-09 (evening 2): Favourite tag, copy reframe, YouTube ToS findings

- **Favourite tag shipped.** New `Track.favourite` (additive column), a heart toggle in the track
  editor, and two settings under Repetition & rediscovery: `favourite_pacing_enabled` (off by
  default, so favourites behave normally) and `favourite_pacing_strength` (1.0–3.0). When enabled,
  a favourite's satiation and rediscovery multipliers are amplified away from neutral, so a
  favourite is rested harder after heavy play and resurfaces more strongly once dormant. Exported
  and imported; unit-tested (`test_favourite_pacing.py`). Currently shared metadata (like
  audio_only), not per-profile — per-user favourites can come later if wanted.
- **Copy reframed** (site bullet, llms.txt, AGENTS.md): dropped "your files, your server, your
  responsibility"; now "a library you already keep, wherever you keep it: local files, a NAS, or a
  home media server such as Plex." Agent docs tell agents to ASK the user where the library lives
  and, if they cannot find it, to ask the user rather than guess.
- **YouTube read first-hand (owner asked).** Findings: embedding via the official IFrame Player API
  IS permitted, but YouTube's ToS forbid the things that make Harmonica Harmonica-like for that
  content — audio-only/hidden video, background play, trimming, ad-stripping, and using YT as a
  standalone music service; and metadata must come from the official Data API, NOT scraping
  ("public properties"). So a compliant YouTube mode = a visible, un-trimmed, ad-inclusive embedded
  player, metadata via the Data API, user supplies their own links/playlists. That is a real but
  much narrower feature than "treat YouTube as your ad-free paced library." HELD for an owner
  decision. Spotify note: reading a
  user's own playlist metadata uses Spotify's FREE Web API (only *playback* needs Premium), which
  is why the lawful route is matching to YouTube and embedding, not integrating Spotify playback.

## 2026-07-09 (evening 3): per-profile favourites, YouTube embed backend, sharing decisions

- **Multi-tenancy base was already complete.** Private per-profile libraries, listening history,
  ratings, saved queues and cover verdicts, import dedupe/redirect onto a shared media pool, and a
  tamper-proof bearer token (Phases 1 to 4 of the multi-user plan) are all built and green.
- **Favourites are now per-profile.** A favourite is one listener's private opinion of a shared
  song, so it moved off the shared `Track` onto the per-profile link (`DeviceConfigTrack.favourite`,
  additive). It flows through the library view, the track editor, the algorithm's favourite pacing,
  and export/import, and a test proves one user's star never leaks onto the shared row or to anyone
  else. Legacy/local (no-profile) mode still uses `Track.favourite` unchanged.
- **Rediscovery copy** reworded twice at the owner's direction, landing on an economics register:
  "increase its weight marginally as it goes unheard, so it plays on a cycle that slows the loss of
  novelty over time." Dropped the earlier "lost for good" implication.
- **Sharing model decided (owner).** The remaining per-profile features, in the agreed build order:
  YouTube embed first (largest), then optionally-shared settings (only surfaced once sharing is
  enabled on the NAS, never otherwise), then cross-user rating influence (the "primary" listener is
  whoever is currently playing the song, other listeners' plays count at a reduced weight that is a
  setting exposed only when the feature is on), then the sharing configuration itself living in a
  server-side config file editable over SSH inside the NAS container, and finally a per-profile
  ignore/hide list (smallest). All sharing controls stay hidden unless enabled on the NAS.
- **YouTube embed backend built (opt-in, compliant, off by default).** New `embeds` table and a
  pluggable `embeds.py` parser that recognises a YouTube link and records the video id plus the
  official `start=`/`t=` offset (a supported player feature, not a modification). A
  `youtube_embed_enabled` setting (default off), a `/youtube/config` endpoint that reports only
  whether embeds are on and whether a key is present, and embeds carried through import/export.
  Playback will use YouTube's official IFrame player on the frontend. Honest code comments state
  the compliance boundary plainly: no audio-only extraction, no ad-stripping, no scraping.
- **Integration keys are protected.** The YouTube Data API key (and, when built, the Spotify keys)
  are read from an env var or a private file under the Harmonica home, never stored in the DB, never
  exported, and never sent to the browser (only a presence boolean is). `AGENTS.md` instructs agents
  not to seek out or read the user's credentials, and deliberately does not say where they live.
- **NAS dedupe note for agents** added to `AGENTS.md`: when setting up a new profile on a NAS that
  already holds other people's songs, rely on the dedupe-on-import so the same file is never stored
  twice.

## 2026-07-09 (evening 4): YouTube embed frontend, kept small and strictly opt-in

### User Input

Asked to build the YouTube frontend. Reviewed `embeds.py` and was content with its size. Direction:
keep the front-end features small and not loaded by default, and **do not send any request to
Google or YouTube from the app unless the user explicitly enables the YouTube player mode**.

### What was built

- A small, self-contained YouTube player path: `youtube.ts` (config type, consent storage, and a
  lazy loader for the official IFrame Player API script), `YouTubePlayer.tsx` (the player plus a
  consent gate), and minimal ambient typings. The shared player hook gained a narrow "external item"
  bridge so a YouTube track parks the local `<video>` element, advances the queue when the video
  ends, and reflects play/pause on the transport bar.
- **Nothing contacts YouTube until two explicit steps happen:** the `youtube_embed_enabled` setting
  is turned on (default off), and the user accepts a one-time consent gate that explains YouTube's
  player loads YouTube, sets its own cookies, and may show ads. Only then is YouTube's script
  requested. The gate and settings copy state plainly that Harmonica does not remove ads or cookies
  and that the video stays visible, as YouTube's terms require.
- A single "YouTube link" field in the track editor (shown only when the feature is on) lets the
  user attach a link, parsed server-side. Without it the feature would be unreachable from the UI.
- Honest limitations recorded: the app's own seek bar and loudness meter do not apply to a YouTube
  video (its audio can't be tapped cross-origin), so YouTube's own controls handle scrubbing.

## 2026-07-09 (evening 5): read-only Spotify playlist import (opt-in, server-side)

### User Input

Asked to build the Spotify connector next, and — because these connectors add attack surface on a
NAS where open ports matter — to run a red-team pass afterwards (2 Sonnet 5 and 2 Opus 4.8 agents:
one of each solo, plus a Sonnet and an Opus collaborating) before the final message.

### What was built

- `spotify.py`: a read-only client over the standard library (no new HTTP dependency). Given a
  public playlist link it reads track names, artists, album, and duration through Spotify's Web
  API. Metadata only. No audio, no scraping, no playback. Off by default.
- Credentials (client id + secret) are handled exactly like the YouTube key: env var or a private
  file under the Harmonica home, never in the DB, exports, logs, or the browser. Every Spotify call
  is server-side, so the browser never contacts Spotify and no cookies are involved.
- Security by construction: the only user input is a playlist reference, validated to a strict
  base62 id before it is placed into a request to a fixed Spotify host. Redirects are refused and
  non-Spotify hosts are rejected, so it cannot be turned into an SSRF against a NAS's internal
  services. Responses are size-capped and time-limited, and the track count is capped at 500.
- Endpoints: `GET /spotify/config` (presence booleans only) and `GET /spotify/playlist?url=` (gated
  on the feature being on AND credentials present). Frontend: a small panel in the Curate tab that
  reads a playlist and flags which songs are likely already in the library. Settings switch added.

## 2026-07-09 (evening 6): red-team of the connectors, then a full security fix + preset redesign

### User Input

After the connectors landed, the owner asked for a red-team pass (the new connectors add attack
surface on a NAS, where open ports matter), then to fix everything it found ("imperative"), and in
parallel to update the listening presets via specialised sub-agents: Codex (via `codex exec`) to
design the most conservative long-run-utility preset with a Sonnet 5 review, Opus 4.8 to update the
other recent presets grounded in behavioural economics with a Sonnet 5 review each, all built
independently, plus a dedicated agent to confirm the Balanced preset is as balanced as it can be.

### Red-team outcome (4 agents: solo Sonnet, solo Opus, and a talking Opus+Sonnet pair)

All four agreed the Spotify SSRF surface is genuinely well-built (no bypass found). The real issues
were access control, now fixed:
- The spoofable `X-Harmonica-Config-Id` header is no longer honoured in exposed mode (identity must
  be a signed token), closing the cross-profile IDOR.
- An authenticated access model: bound off loopback (a NAS on 0.0.0.0) or with `require_auth` forced
  on, every non-public endpoint needs a valid profile token. Local (loopback) use is unchanged.
- A CSRF guard (Sec-Fetch-Site / Origin) that refuses cross-site browser requests to state-changing
  endpoints and to `/spotify/playlist` — this protects even the default local install, and does not
  affect non-browser clients. Implemented as pure-ASGI middleware so media range requests (audio and
  video seeking) still work.
- Embed ids supplied as provider+id are now format-validated (not only when parsed from a URL); the
  embed fields and list are length-bounded.
- `secret.key` is written 0600 (rotating it revokes all tokens); the absolute home path is no longer
  returned by `/settings`; a strict Content-Security-Policy and related headers are sent on every
  response. Remaining follow-up: exposed-mode front-end UX (prompt to claim on a 401) and optional
  per-token expiry/revocation, both noted as non-blocking.

### Preset redesign (designed independently, each reviewed by Sonnet 5)

The four presets now each set the full knob set (including the newer satiation / rediscovery /
favourite-pacing controls), so switching presets fully overrides the previous one. Highlights the
reviews caught: the Familiar design had favourite-pacing amplifying an already-floored satiation
term, which would have rested favourites *harder* than neutral (disabled it); Discovery's anti-repeat
knobs had drifted into the most-conservative preset's territory (separated them); the dedicated
Balanced audit found the shipped defaults were not maximally neutral (the cooldown floors cloned
Discovery's aggressive values and visual-priority baked in a non-taste video lean), so Balanced was
re-centred (higher cooldown floors, visual multiplier neutralised to 1.0).

## 2026-07-09 (evening 7): in-app YouTube setup notes, then a video-list importer

### User Input

Two threads. First, the owner asked that the YouTube *setup* stage carry the practical notes a user
needs before enabling playback: how YouTube's cookies and consent work, an honest note that a
content blocker (uBlock Origin) is the user's own browser choice since Harmonica uses YouTube's own
player and removes nothing, and that YouTube's loudness levelling ("Stable Volume") is YouTube's to
control, not ours. Also a factual question: the Data API key is server-side, so how does the user
first give it to the server? (Answer: only an env var or a private file today, which is friction.)

Second, and larger: build a **YouTube video-list importer**, where the user pastes a big list of
video links and the app organises them into tracks by metadata and properties. Agreed shape:

- **Factor picker.** The user ticks which factors to organise by. Keyless factors (uploader, title)
  use YouTube's official oEmbed endpoint and need no key. Key factors (duration, description,
  category, tags, publish date) use the Data API. The moment a key factor is ticked with no key set,
  the app explains, *then and only then*, how to get a key and where to place it. No key field in the
  browser: the secret still arrives only by env var or private file (the owner's choice).
- **Two-stage organising.** Stage one is always safe: one proposed track per readable video, with
  the uploader as a group (the reliable signal), the title parsed into artist/title, and the link
  attached. Stage two suggests same-song clusters from order-insensitive title overlap and, when the
  description factor is on, a song title appearing in another video's description. Every cluster is
  shown for the user to confirm and is never applied on its own.
- **Honest limit.** Lyric/subtitle overlap was requested as a clustering signal but dropped: caption
  text is not retrievable for third-party videos, so faking it would mislead. Title and description
  overlap are the workable signals.

### Outcome

Delivered. The YouTube playback settings section now carries the cookies / tracking-is-yours /
loudness notes. The importer is server-side (`youtube_import.py` fetch with the same fixed-host,
no-redirect, size/time-capped guards as the Spotify client; the Data API key travels in an
`X-goog-api-key` header so it never lands in a URL or a log), `youtube_organize.py` does the pure
organising, and `POST /youtube/import-preview` returns proposed tracks that flow into the existing
review-before-import screen. The importer UI shows no video thumbnails, so the browser makes no
request to Google during import, consistent with "nothing reaches YouTube until the user opts in".
The endpoint inherits the CSRF and exposed-mode token guards (tested), so it stays safe on a NAS.

## 2026-07-10: Versioning, public README, watch-time framing, and pre-publish polish

### User Input

A cluster of go-public decisions. **Versioning:** the owner designed a milestone scheme — `v0.x.1`
opens a milestone band ("exists but doesn't work", "works at the minimum", "trusted with my own
library", and so on) and later patch numbers are the marginal changes inside the band. Agreed to
express it as annotated git tags on the existing commits rather than rewriting messages, and to
keep tags separate from GitHub Releases: no Release exists until there is something a non-technical
person can actually run. `v1.0.0` is defined as that first runnable artifact, not a date, and will
exist before the project is publicised.

**README:** rewritten for humans first. The owner's insight: agents that read a file whole see it
truncated with most weight at the tail, so the agent-facing section belongs at the END of the
README, and the human pitch at the top. Licence sits just above it. The manual setup path was cut
in favour of double-click start scripts (`start-harmonica.bat` / `start-harmonica.sh`), which are
also the seed of the 1.0.0 artifact. The player opens at `localhost:8765` (friendlier than an IP;
dropping the port is not worth requiring admin rights).

**Watch-time framing:** the owner wanted the site and README to name the incentive difference —
the big platforms maximise watch time, which can come at the cost of long-term enjoyment, while
Harmonica gains nothing from watch time. An earlier draft said Harmonica "does not measure it";
the owner corrected this since the app does keep local listening history for the cooldowns. The
final wording — "gains nothing from your watch time, and does not maximise it" — says only what is
true.

**Deferred, by owner decision:** UI themes (the green stays untouched as the default; fully dark
and fully white to be added, amongst others) and an in-browser demo at a test subdomain — the real
engine compiled to WebAssembly on a static page, where the user pastes YouTube links to build
their own throwaway library (no pre-baked library), with an honest note that the local version is
better. Both parked until after the repo is public.

### Outcome

Nine tags (`v0.0.1`–`v0.7.1`) pushed at the band boundaries. README rewritten and trimmed to the
owner's register. Site, llms.txt, and copy file carry the corrected watch-time paragraph. Along the
way the owner asked whether YouTube fullscreen survives a queue advance: it did not (the player was
destroyed and rebuilt per video, which forces the browser out of fullscreen), so the player is now
created once and videos are swapped in place, the same way YouTube's own playlists keep fullscreen.
The paused-video "More videos" shelf stays: `rel=0` already limits it to same-channel suggestions,
and the only ways to remove it outright would breach the embed terms the feature is built to honour.

## 2026-07-10: The 1.0.0 release, and first contact with a fresh machine

The owner started the cold-machine test on a second computer (Windows) and asked for the first
release in parallel: v1.0.0, whose artifacts are small installer scripts that download Harmonica
and set it up for a first start. One for local use, one for a NAS. Nothing for Android yet.

**Fresh-machine lesson:** the local agent on the Windows machine set the project up in development
mode and pointed the owner at the Vite dev server on port 5173, instead of building the UI and
serving everything from the daemon at `localhost:8765`. Nothing in the repo told it to do that; it
found Vite on its own. `AGENTS.md` now says explicitly that the single origin is the app and the
dev server is only for working on the UI itself.

**Curate placement (logged for later):** once the library holds local songs, the Curate page should
be opened from Settings rather than sitting in the sidebar. Curation is an occasional act, not a
daily surface.

### Outcome

Three installers in `install/` (Windows local, Linux/macOS local, NAS), each of which downloads the
tagged source into the home folder and hands over to the start scripts, with the NAS one binding
`HARMONICA_HOST=0.0.0.0` and printing the LAN address. The README's "Running it" now leads with the
releases page. Tag `v1.0.0` marks the release, with the installers attached as release assets.

## 2026-07-10 (later): Polish round — WHO link, YouTube discoverability, settings guard, themes

While testing the fresh-machine flow, the owner sent a polish list. Link the WHO from the
listening-health insight. Drop "and takes no position on it" from the YouTube settings copy.
Make switching YouTube on actually surface where the links are pasted, since the feature was so
hidden you could not tell what the setting did or that the feature existed. Ask before leaving
Settings with unapplied changes, whichever way you leave. Give the bottom bar a slightly
different colour from the sidebar, growing into a sketch of theme customisation: three colour
slots (main, sidebar, player bar) from a limited range plus a dark mode. Limited deliberately,
in the owner's words, because with unlimited colours "you make the background black, you can't
read black text on it, and we don't have anything that would fix that". The owner also asked
for every UI line that does not appear by default to be collected for manual text review.

### Outcome

An Appearance section in Settings: swatch pickers for background (5 light options), sidebar and
player bar (6 dark options each), plus a dark mode switch. Device-side (localStorage), applied
instantly as CSS variables, with the player bar now defaulting to a deeper "Ink green" than the
sidebar. Dark mode flips the surface variables and overrides the audited set of hardcoded light
tints, so every combination keeps text readable. Leaving Settings with unapplied changes now
raises an apply / discard / keep-editing prompt (with the browser's own warning on tab close).
Turning the YouTube switch on reveals a pointer with a button to the Curate page. All verified
in a scripted headless-browser pass. The not-visible-by-default strings now live in
`docs/planning/copy-app-hidden.md` for the owner's review.

## 2026-07-10 (later still): Website review round, llms.txt as a reader-aware document

The owner reviewed the public site against a screenshot and sent a detailed list. The hero was
misaligned (its paragraph sat further left than the section below, traced to a CSS shorthand
wiping the container's horizontal padding). Copy notes: split the long "Why" sentence and let
"The rest of your library remains untouched" stand alone, demote the bold summary sentence to
italics since "it wasn't written by me, so it should certainly not be more visible than the text
that was", swap "because" for "Especially as" in the watch-time line, state the v1.0.0 release
on the PC and NAS platform lines, soften "require this" to "benefit from this", and address the
setup note directly to the reader, ending "if you are in fact a Large Language Model: a
machine-readable summary of this site lives at /llms.txt". The small print and contact line
shrink, with no explanation needed for the latter.

The llms.txt notes show deliberate reader-awareness for a machine audience: no hard line breaks
(one line per paragraph, wrapping is the reader's job), no Android release listed because "it can
confuse agents (it doesn't exist yet)", no "and let it" because "the agent knows it is an agent",
and the Legal section moved between What it does and How it runs because LLMs weight the end of a
file most, "we should not stress them out further". The owner also asked whether robots.txt must
link the llms.txt convention (it does not, so the link went), whether releases track newer
commits (they do not, installers download the tagged snapshot, and this tag will be re-pointed
once the current round lands), and for a local Important_Before_Release reminder about keeping
the site and llms.txt in step with releases. The satiation guard line earned a commendation.

In the app, the YouTube pointer that appears when the switch is turned on now also walks through
the import steps (properties read, review before landing, official player). In parallel the
owner asked for appearance presets and for settings to be organised into simple and complex
tiers behind a checkbox, delegated to a sub-agent working in an isolated worktree.

## 2026-07-10 (evening): Contributor guidance and the spec's provenance

A public-docs review round. CONTRIBUTING.md now asks agents to get their user's permission
before doing anything, requests that issues and pull requests be organised by what they do
(bug report, adding a setting or preset, adding to the algorithm, additional integration,
added feature, amongst others), and writes the licence line as "GNU AGPL-3.0 or later" without
the run of dashes. The Android deployment line left CONTRIBUTING and the README, matching the
llms.txt decision that a platform which does not exist yet should not be listed.

Two corrections to `harmonica_algorithm_spec.md` from the owner's read-through. The section
titled Pseudocode was in fact working Python, and now says so. And the document read as if the
assistant had designed the algorithm with occasional inputs, when it was actually the surviving
record of a long design exchange the owner drove, so a Provenance section now states plainly who
set the problem, who supplied the economic framing, and how each mechanism in section 3 had to
earn its place. The recommended defaults were verified against the shipped implementation (all
core values still hold, with a note pointing at GET /settings as the live source of truth) and
the rating section carries an update note for the five-star mapping that shipped later.

### Outcome (appearance presets and settings tiers)

Delivered by the delegated agent and merged after review. Six appearance preset chips sit above
the swatch rows (Classic, Charcoal, Espresso, Midnight, Plum, Night), each applying a full
colour combination instantly, with the chip highlighting only while the live selection matches
it exactly. Settings now open on the simple tier (Queue, Coverage, Visuals, Hearing health,
Explanations, YouTube, Spotify, Appearance) and a Show complex settings switch in the right-hand
panel reveals the fine-tuning sections. Hiding is display-only, so Apply changes, Reset and the
leave guard still cover every value. The merge itself needed care: the automatic merge had
placed the new YouTube import steps under every section heading, caught in review and verified
fixed in a scripted browser pass.

## 2026-07-10 (night): Second thoughts on framing, and YouTube out of sight when off

Three refinements. The site's watch-time line had grown a conditional it never meant: "Especially
as it gains nothing from it" could be read as saying the only reason Harmonica does not track
listening is that there is nothing in it, so it now reads "It is built for the long term instead",
with the matching llms.txt line aligned. The owner supplied a tightened AGENTS.md (shorter intro,
a leaner credentials sentence) which replaced the previous one verbatim. And a standing rule was
made explicit: YouTube should barely appear anywhere in the app unless the feature is enabled.
An audit confirmed the player, consent gate, library editor link field, Curate import panel and
settings pointer were already gated on the switch. The one leak was the settings section's large
"Before you turn this on" card, which now folds behind a single "Setup notes: cookies, ads, and
loudness" line, leaving the switch and two quiet lines as YouTube's whole footprint while off.
Verified in a scripted browser pass: notes folded by default and opening on click, no YouTube
field in the editor, and zero mentions of YouTube on the Curate page while the switch is off.

The owner also asked for an independent critical review of the algorithm spec, unconvinced that
the first round of fixes did more than add annotations. A reviewer agent was given the owner's
verbatim concerns and the goals, with its suggested edits to be applied after review.
