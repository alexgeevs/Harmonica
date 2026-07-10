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
- Pick at least one song, or choose “All songs”.
- Could not claim that profile. *(fallback)*
- Could not create that profile. *(fallback)*

## Banner: active profile (App.tsx, above the view while a profile is active; the empty-library suffix is already in copy-app.md)

Profile **{name}** is active · {N} songs in your library. — with button: Switch to local

## Banner: loudness warning (App.tsx, appears while sustained playback level is above the warning threshold)

Sustained loudness looks high [for compressed audio]. Consider turning it down to protect your
hearing. *(relative estimate)*

## Insights: listening health, before any samples (App.tsx)

Loudness is measured live while you listen. Play a few tracks and your average and peak levels
will appear here.

## Insights: listening health, note under the bars (App.tsx; "WHO" is now a link to who.int/activities/making-listening-safe)

Relative estimates, not calibrated dB — browsers can't read true sound pressure. The WHO suggests
~80 dB for 40 h/week as a safe ceiling; each +3 dB halves the safe time. Treat these as a nudge,
not a measurement.

## Cover comparison card (App.tsx, appears while the second rendition of an A/B pair plays)

- Heading: Which version is better?
- Body: You're hearing a second take of **{title}**. Compare it with the one just before it.
- Vote buttons: The first was better · About the same · This one's better
- Replay button: ▸ Replay {first title} to compare

## "Why this song" reasons (format.ts, one or more shown per playing track depending on algorithm state)

- Drawn from {group name} ({N} tracks)
- You rate this highly
- You rate this lower than most, so it comes up less often
- A favourite you haven't heard in a while — bringing it back fresh
- The original recording
- Your favourite rendition of it
- New to you — surfaced early so you can rate it
- You've played this a lot lately — resting it so it doesn't wear out
- You heard this exact song recently
- Eased off {group name} for variety
- Has a video — easier to review while you're here
- Recently skipped, so it's eased off for now
- Another version of this song played recently
- A balanced pick for variety

## "Why this song" maths labels (format.ts, only with "show the maths" on)

Manual nudge · Your rating · Skip history · New-song boost · Played a lot lately · Dormant
favourite · Has a video · Resting this song · Resting this version

## Settings: leave with unapplied changes (App.tsx, NEW modal when navigating away from a dirty Settings page)

- Heading: Apply your changes?
- Body: You have changed settings but not applied them yet.
- Buttons: Apply and continue · Discard changes · Keep editing

## Settings: YouTube pointer (App.tsx, NEW, appears under the YouTube section while its switch is on; "Curate page" is a button that navigates there)

**YouTube playback is on** — Paste a list of YouTube links on the Curate page and each link
becomes a song, or open one song in the library editor and paste its link there. [if unapplied:]
Apply your changes first.

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
- Factors (label — hint): Uploader — Group by who uploaded it. · Title — Split “Artist - Title”
  and spot covers or live versions. · Duration — Flag videos too long to be a single song. ·
  Description — Match the same song across differently titled videos. · Category — Flag videos
  YouTube does not class as music. · Tags — Read the uploader's tags. · Publish date — Read when
  each video went up.
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
- Result line: {playlist name} — {N} track[s] · {N} in your library
- Truncation note: Only the first 500 tracks were read.
- Owned tag (tooltip: Likely already in your library): in library
- Error fallback: Could not read that playlist

## Settings: Appearance section (App.tsx, NEW; visible by default but listed here as it is new this round)

- Note: Colours for this device. They apply immediately, with no need to press Apply changes.
  The choices are limited on purpose, so text stays readable on every combination.
- Rows: Background · Sidebar · Player bar · Dark mode
- Surface names: Mint · Paper · Sand · Sky · Blossom
- Bar names: Deep green · Ink green · Charcoal · Midnight · Plum · Espresso
- While dark: Dark mode sets its own background.
