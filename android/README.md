# Harmonica for Android (native Kotlin)

A native Android client for the Harmonica daemon. It has its own mobile UI but shares the backend,
algorithm, and library on your always-on machine (laptop/mini-PC/Pi). On Android it can do what the
web app cannot: **read the system volume and the active output device** (wired / Bluetooth / speaker)
for a far better hearing-health estimate, play in the background, and (later) keep a local song folder
for offline listening that syncs with the daemon.

## Status — scaffold (not yet built/verified)

This was authored in an environment without the Android SDK, so it **has not been compiled**. It is a
coherent starting point: open it in **Android Studio** (Koala or newer), let it sync Gradle, and
expect to fix a few versions/imports. The pieces that encode real project knowledge — the API client
matching the daemon, the data models, the `AudioManager` loudness monitor — are the valuable part.

## What's here

- `app/` — single-module Compose app.
  - `data/HarmonicaApi.kt` + `ApiModels.kt` — Retrofit client mirroring the daemon's real endpoints
    (`/configs/claim`, `/queue/generate`, `/tracks`, `/playback-events`, `/media/{id}`).
  - `data/HarmonicaClient.kt` — Retrofit/OkHttp builder + a small repository.
  - `data/Prefs.kt` — DataStore for the daemon base URL + claimed `config_id`.
  - `player/PlayerController.kt` — Media3/ExoPlayer playback streaming from `/media/{assetId}`.
  - `audio/LoudnessMonitor.kt` — reads `STREAM_MUSIC` volume + output device type; estimates relative
    exposure (still not calibrated dB SPL, but uses real device signals).
  - `ui/AppScreen.kt` — connect screen (daemon URL + config name + passphrase) and a now-playing/queue
    screen.

## Build

1. Install Android Studio + an SDK (API 34+).
2. `File → Open` this `android/` folder.
3. Generate the Gradle wrapper if missing: `gradle wrapper` (or let Studio do it).
4. Put your daemon on the LAN: run the server with `harmonica serve --host 0.0.0.0`, give the machine a
   DHCP reservation (or use mDNS `harmonica.local`), and enter `http://<ip>:8765` in the app.

## Roadmap (see ../docs/planning/multi-device-architecture.md)

- [x] Daemon API client, config claim-by-passphrase, queue generation, streaming playback.
- [x] System-volume + output-device monitoring for hearing health.
- [ ] Local media folder + offline cache; delta sync of ratings/playback events on reconnect.
- [ ] Rating + curation screens; background playback service + media notification.
- [ ] mDNS discovery of the daemon.
