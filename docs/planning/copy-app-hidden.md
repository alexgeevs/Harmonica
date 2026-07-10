# App UI copy that does not appear by default (edit in place)

These are the lines you will not see by casually browsing the app: they need an error, an empty
or unusual state, a gated feature turned on, or a particular moment in playback. Edit the text
under each heading; the headings say where each string lives and when it shows, so edits can be
applied back to the source files. Lines already listed in `copy-app.md` are not repeated here.

---

## Errors: request failures (App.tsx, shown in the top bar; each is the fallback when the server gives no message)

- Could not generate a queue
- Could not load that queue
- Could not rename that session
- Could not delete that session
- Could not save the rating
- Could not save the track
- Could not save settings

## Errors: device profile (App.tsx, settings side panel)

- Name and passphrase are both required.
- Pick at least one song, or untick pre-filling.
- Could not claim that profile. *(fallback)*
- Could not create that profile. *(fallback)*

## Profile panel: create-mode hints (App.tsx; which one shows depends on the "Let new profiles pick songs" setting)

- Picker off (the default): A new profile starts with an empty library. Import or scan songs once
  it is active. To let new profiles pick songs from this library instead, turn on "Let new
  profiles pick songs" in the settings list.
- Picker on, pre-fill unticked: Unticked: the profile starts with an empty library and imports
  its own songs.
- Picker on, checkbox label: Pre-fill from this library
- Picker list overflow: Showing the first 300. Search to narrow.
- Active profile with no songs, side-panel tag: No songs yet

## Banner: active profile (App.tsx, above the view while a profile is active; the empty-library suffix is already in copy-app.md; followed by button: Switch to local)

Profile **{name}** is active · {N} songs in your library.

## Banner: loudness warning (App.tsx, appears while sustained playback level is above the warning threshold)

Sustained loudness looks high [for compressed audio]. Consider turning it down to protect your
hearing. *This is a relative estimate, not an exact measurement.*

## Insights: listening health, before any samples (App.tsx)

Loudness is measured live while you listen. Play a few tracks and your average and peak levels
will appear here. They are relative estimates, not exact measurements.

## Insights: listening health, note under the bars (App.tsx; "WHO" is now a link to who.int/activities/making-listening-safe)

Relative estimates, not calibrated dB, because browsers can't read true sound pressure. The WHO
suggests ~80 dB for 40 h/week as a safe ceiling; each +3 dB halves the safe time. Treat these as
a nudge, not a measurement.

## Cover comparison card (App.tsx, appears while the second rendition of an A/B pair plays)

- Heading: Which version is better?
- Body: You're hearing a second take of **{title}**. Compare it with the one just before it.
- Vote buttons: The first was better · About the same · This one's better
- Replay button: ▸ Replay {first title} to compare

## "Why this song" reasons (format.ts; at most three lines per playing track: where it came from, the single strongest boost, the single strongest damper)

- Line 1, source: Drawn from {group name} ({N} tracks)
- Line 2, one boost, whichever multiplier is largest:
  - You rate this highly
  - A favourite you haven't heard in a while
  - New to you, surfaced early so you can rate it
  - The original recording, out of {N} versions
  - Your favourite of {N} versions
  - Has a video, easier to rate on screen
- Line 3, one damper, whichever multiplier is smallest, always prefixed "Coming up less often
  right now:" because a damper lowers a song's odds rather than blocking it (this song was still
  picked):
  - you rate it lower than most
  - it has had a lot of play lately
  - you heard it recently
  - you skipped it recently
  - another version of it played recently
  - {group name} has played a lot recently
- Fallback when nothing stands out: A balanced pick for variety

## "Why this song" maths labels (format.ts, only with "show the maths" on)

Manual nudge · Your rating · Skip history · New-song boost · Played a lot lately · Dormant
favourite · Has a video · Heard recently · Version heard recently

## Settings: leave with unapplied changes (App.tsx, NEW modal when navigating away from a dirty Settings page)

- Heading: Apply your changes?
- Body: You have changed settings but not applied them yet.
- Buttons: Apply and continue · Discard changes · Keep editing

## Settings: YouTube setup notes disclosure (App.tsx; the notes card with "Before you turn this on" is now folded behind this clickable line, so only the line shows by default. The card's text is unchanged and lives in copy-app.md)

Setup notes: cookies, ads, and loudness

## Settings: YouTube pointer (App.tsx, appears under the YouTube section while its switch is on; heading then body; "Curate page" is a button that navigates there)

- Heading: YouTube playback is on
- Body: Paste a list of YouTube links on the Curate page and each link becomes a song, or open
  one song in the library editor and paste its link there. [if unapplied:] Apply your changes
  first.

- **Importing reads each video's properties.** Harmonica reads the links' metadata on the server,
  the uploader and title by default and more with a Data API key, and organises them into tracks.
  Nothing is downloaded.
- **You review before anything lands.** The organised tracks appear as a proposal on the Curate
  page, where you check them and apply the ones you accept.
- **Playback stays official.** Each imported song plays through YouTube's own embedded player.

## YouTube consent gate (YouTubePlayer.tsx, replaces the player until accepted, only with YouTube playback on)

- Heading: Play this song on YouTube?
- Body: This song plays through YouTube's official player. Loading it contacts YouTube, which
  sets its own cookies and may show ads. Harmonica does not remove either. Nothing is requested
  from YouTube until you accept.
- Button: Load the YouTube player
- Footnote: You can turn YouTube playback off again in Settings.

## Curate: result banners (CurateView.tsx)

- Applied {N} change[s].
- Nothing new to import. Your library already matches this. *(also in copy-app.md)*
- Could not read that proposal *(fallback)* · Could not read that file *(fallback)* · Export
  failed *(fallback)* · Apply failed *(fallback)*

## Curate: diff review controls (CurateView.tsx, only while a proposal is loaded)

- Summary: **{N}** changed · **{N}** new · **{N}** unchanged [· {N} not in proposal]
- Buttons: Accept all · Clear · Cancel · Apply {N}
- Row tooltip: Accept this change

## YouTube import panel (YouTubeImportPanel.tsx, on Curate only while YouTube playback is on)

- Heading: Import from a list of YouTube links
- Body: Paste video links (one per line, or separated by spaces). Harmonica reads their metadata
  on the server and organises them into tracks for you to review. The video plays later through
  YouTube's official player. Nothing is downloaded.
- Factor picker legend: Organise by
- Factors (label, then hint):
  - Uploader: Group by who uploaded it.
  - Title: Split “Artist - Title” and spot covers or live versions.
  - Duration: Flag videos too long to be a single song.
  - Description: Match the same song across differently titled videos.
  - Category: Flag videos YouTube does not class as music.
  - Tags: Read the uploader's tags.
  - Publish date: Read when each video went up.
- With a key set: Using your Data API key for the factors marked “key”.
- Key help heading: Those factors need a YouTube Data API key
- Key help body: The factors marked “key” read extra detail through YouTube's Data API, which
  needs your own key. The keyless factors (uploader and title) work without one.
- Key help steps: 1. Create a free key in the Google Cloud console. Enable “YouTube Data API
  v3”, then make an API key. 2. Give it to the server. Either set the environment variable
  HARMONICA_YOUTUBE_DATA_API_KEY before you start it, or put the key in a file named
  youtube_data_api.key inside the Harmonica home folder (.harmonica by default). Reload
  afterwards.
- Key help footnote: Until then, leave the “key” factors unticked to import with the uploader
  and title only.
- Read button: Read and organise
- Result line: **{N}** track[s] organised from {N} link[s] [· {N} could not be read] [· read
  with your Data API key]
- Truncation note: Only the first batch was read. Import these, then paste the rest.
- Cluster prompt: These look like the same song. Tick any you want grouped as one version
  family, after checking them.
- Unreadable video row: Could not read this video
- Non-song flag (tooltip: May not be a song): check
- Review button: Review {N} track[s] before importing
- Error fallback: Could not read those links

## Spotify panel (SpotifyPanel.tsx, on Curate only while Spotify is on)

- Heading: Compare a Spotify playlist
- Body: Paste a public playlist link to see which of its songs you already have. Track names
  only, read through Spotify's Web API. No audio is downloaded.
- Read button: Read
- Result line: **{playlist name}** then, beside it: {N} track[s] · {N} in your library
- Truncation note: Only the first 500 tracks were read.
- Owned tag (tooltip: Likely already in your library): in library
- Error fallback: Could not read that playlist

## Settings: Appearance section (App.tsx; visible by default but listed here as it changes often)

- Note: Colours for this device. They apply immediately, with no need to press Apply changes.
  The choices are limited on purpose, so text stays readable on every combination.
- Preset chips (each applies a full combination): Classic · Charcoal · Espresso · Midnight ·
  Plum · Night · Ember (Night is plain dark; Ember is warm dark with espresso bars)
- Rows: Background · Sidebar · Player bar · Dark mode · Dark tone (the last only while dark)
- Surface names: Mint · Paper · Sand · Sky · Blossom
- Bar names: Deep green · Ink green · Charcoal · Midnight · Plum · Espresso
- Dark tone names: Neutral · Warm · Green
- While dark, under Background: Dark mode sets its own background.
- While dark, under Dark tone: Neutral is a plain dark. Warm leans amber, which sits easier with
  night-time viewing. Green matches the classic look.

## Settings: complex tier (App.tsx; the toggle is visible by default in the right-hand panel, but the sections it reveals are hidden until it is on)

- Toggle label: Show complex settings
- Toggle helper: Off keeps the list to the everyday controls. On reveals the fine-tuning knobs.
- Sections hidden until on: Recommendation core · Anti-repetition & variety · History & feedback ·
  Rating normalisation · Repetition & rediscovery · Covers · More (their control copy is already
  in copy-app.md)
- Simple section: Queue, with the note: How many songs a freshly generated queue holds.

## Settings: Device profiles section (App.tsx + settings_store.py, NEW; the section is visible by default, the behaviour it gates is in the profile panel)

- Section note: What creating a new profile in the panel to the right may see. Off keeps the
  song list hidden from whoever is creating a profile, which matters when this install is shared
  over a network.
- Control label: Let new profiles pick songs
- Control description: When on, the create-profile form offers a picker that lists every song in
  the library. Off hides that list, so creating a profile on a shared or networked install does
  not reveal which songs exist. New profiles then start empty and import their own songs.
