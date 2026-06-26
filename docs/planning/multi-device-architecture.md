# Multi-Device, NAS Hosting, Android, and Cross-Device Sync

This document answers the feasibility questions and proposes an architecture for running Harmonica
across several devices, with an Android client and shared config/library. It is a plan; only the
pieces marked "implemented" exist today.

## Can a bare HDD plugged into the Wi-Fi router run Harmonica? — No.

A USB hard drive attached to a consumer router only **serves files** (SMB/DLNA). It has no CPU or OS
of its own to run code. Harmonica's daemon is a Python (FastAPI) process that runs the recommendation
algorithm and a database — that needs an actual computer. Since the router's firmware is closed, the
router can't run it either.

**So you need one small always-on computer.** The HDD can still hold the media files and the SQLite
DB; the compute is separate. Options, cheapest first:

- **Raspberry Pi 4/5 (recommended).** ~$50–90, ~3–5 W, silent, always on. Runs the daemon; media can
  live on a USB drive on the Pi, or on the router's HDD mounted over SMB. This is the simplest "NAS-
  like" setup that actually runs the algorithm.
- **A real NAS that runs containers (Synology/QNAP with Docker).** Turnkey, more expensive; run
  Harmonica as a container, media on the NAS volumes.
- **An old laptop or a mini-PC (Intel N100 class).** Cheap, more than powerful enough, can sleep/wake.

The router's HDD is fine as the **storage** layer (media + DB file); one of the above is the
**compute** layer. They can be combined (Pi + the HDD).

## Recommended model: one daemon, many thin clients (server-authoritative)

Run **one** Harmonica daemon on the Pi/NAS. It owns the canonical library, ratings, history, and DB.
Every device — desktop browser, phone — is a thin client over the LAN. This is the key simplification:

- **No database sync or merge conflicts.** There is one DB. Ratings/history are shared instantly.
- Cross-device "sync" (#4) becomes "point your browser at the daemon." The current web app already
  works this way; it just needs to bind to the LAN instead of localhost.

Today the daemon binds to `127.0.0.1`. For LAN use, run it on `0.0.0.0` (e.g.
`harmonica serve --host 0.0.0.0`) behind the passphrase scheme below. (Implemented: the `--host` flag
already exists; LAN exposure is opt-in.)

### Finding the daemon after the IP rotates

DHCP can change the daemon's IP. Fixes, best first:

1. **DHCP reservation / static IP** for the Pi/NAS (set once in the router) — the address never changes.
2. **mDNS** (`harmonica.local`) so clients find it by name regardless of IP (Avahi/Bonjour).
3. Client-side subnet scan as a fallback.

## Per-device config with passphrase recovery (#2's "config" request)

A **config** = (algorithm settings snapshot) + (**exactly which songs are included**) + a name. Each
config is protected by a **short passphrase**. When a device's IP rotates or a new device joins, it
re-claims its config by typing the passphrase — not by remembering an IP.

Proposed additive schema (server-authoritative, no migration needed):

- `configs(id, name, passphrase_hash, settings_json, created_at, updated_at)`
- `config_tracks(config_id, track_id, included)` — the per-config song selection.

Endpoints:

- `POST /configs` `{name, passphrase, settings, track_ids}` → create.
- `GET /configs` → names only (no secrets).
- `POST /configs/claim` `{name, passphrase}` → returns `{config_id, settings, included_track_ids}`.
- `PATCH /configs/{id}` (with passphrase) → update settings/selection.

Generation then takes an optional `config_id` and only draws from that config's included songs. The
client stores `config_id` locally; if lost, re-claim via passphrase. (Security: the passphrase is a
light LAN convenience lock — hash with PBKDF2, rate-limit claims; it is not strong auth for the open
internet. Keep the daemon on the LAN.)

## iOS app — installable web app (chosen 2026-06-26)

The user has no Mac and doesn't want an Apple Developer account, so iOS ships as an
**installable web app (PWA)**, not a native build. Reality check that drove this:

- **Any** iOS app — native *or* a web-wrapper (Capacitor/Tauri) — must be compiled and
  code-signed with Xcode, which only runs on macOS. You can rent macOS at build time
  (EAS Build, Codemagic, GitHub `macos-latest` runners) so a Mac isn't strictly required,
  but installing on your own iPhone beyond a 7-day re-sign needs a $99/yr Apple Developer
  account. The user opted out of that ceremony for now.
- A PWA sidesteps all of it: open the web app in Safari → Share → **Add to Home Screen**.
  It launches standalone (no browser chrome) and points at the LAN daemon like any client.
- **Trade-off:** Safari gives a PWA no access to system volume or the output-device type,
  so iOS hearing-health falls back to the in-app **signal-based loudness meter** (the same
  Web-Audio RMS estimate the desktop web app uses) rather than the volume×output estimate
  the native Kotlin Android client gets. Acceptable; revisit if a Mac appears.

**Implemented (2026-06-26).** The web app is now a real installable PWA:
`web/public/manifest.webmanifest` (standalone, deep-green theme, maskable icons),
Apple touch icon + `apple-mobile-web-app-*` meta in `web/index.html`, a conservative
app-shell service worker (`web/public/sw.js`, registered prod-only, never caches the API
or `/media`), generated PNG/SVG icons (`web/scripts/make_icons.py`, no image-lib
dependency), and a hardened mobile layout (safe-area insets for the notch/home indicator,
`100dvh`, icon-only top nav, bottom-docked player). Same install works on Android Chrome.

**LAN caveat — secure context.** Service workers register only over HTTPS or `localhost`.
Over a plain `http://<nas-ip>` LAN address: iOS *Add to Home Screen* and standalone launch
still work (it's a manual Safari action), but the offline-shell SW won't activate (it fails
gracefully — no breakage, just no shell caching) and Android Chrome won't offer an install
prompt. To get the SW + Android install, put TLS in front of the daemon — easiest options:
a local CA via `mkcert`/Caddy, or Tailscale (which hands out HTTPS hostnames per device).

**Upgrade path if a Mac/Developer account later appears:** wrap the same React UI with
Capacitor + a ~30-line Swift plugin exposing `AVAudioSession.outputVolume` and route
changes — this recovers the system-volume read without a from-scratch SwiftUI app. (iOS
*does* expose those APIs natively; only the browser sandbox withholds them.)

## Android app — three routes (a decision is needed)

| Route | Reuse | System volume / headphone read | Effort |
| --- | --- | --- | --- |
| **A. PWA** (installable web app) | Full (this React UI) | **No** — browsers can't read system volume/output device | Low |
| **B. Capacitor/Tauri wrapper + small native plugin** | High (same UI) | **Yes** via a tiny `AudioManager` plugin | Medium |
| **C. Native Kotlin app, its own UI** | Backend/algorithm only | **Yes**, fullest (`AudioManager`, output-device callbacks, `MediaSession`, background service) | High |

Notes:

- You asked for the app to read system volume and headphones. A **PWA cannot** do this on Android; a
  **Capacitor plugin or native app can** read the `STREAM_MUSIC` volume index and the output device
  type (wired/Bluetooth/speaker). That makes the hearing-health estimate much better than the
  browser's signal-only guess — though even native Android still cannot read calibrated dB SPL.
- "Songs stored in a folder on the phone" + "sync with the NAS": the app keeps a local media folder
  and a cached config, plays offline, and **delta-syncs** with the daemon when back on the LAN.

## Cross-device DB compatibility & sync (#4)

- SQLite is already a single portable file, and the **JSON library export/import** (now including
  trim points and audio-only) is the portable, agent-friendly interchange format. (Implemented.)
- Keep the **daemon authoritative**. The phone, when offline, caches a read copy and **queues**
  offline events: new ratings and playback events (the latter are append-only, so trivially
  syncable). On reconnect it replays the queue to the daemon. This avoids true multi-master merge.
- For any field that two devices could edit while both offline, resolve last-write-wins by
  `updated_at`. Add `updated_at` where missing as sync is built (tracks already has it).

## Suggested rollout

- **Phase 1 (backend, additive) — DONE.** `device_configs` + `device_config_tracks` tables;
  `GET/POST /configs`, `POST /configs/claim`, `PATCH /configs/{id}`; PBKDF2 passphrase hashing;
  per-config song inclusion in `POST /queue/generate` via `config_id`; settings snapshot per config.
  Tested in `tests/test_api.py`.
- **Phase 2 (web) — TODO.** A "connect / claim config" screen; library and queue respect the
  config's included songs; a per-device settings view.
- **Phase 3 (Android) — STARTED (chose native Kotlin).** Scaffold in `../android/` (Compose UI,
  Retrofit client to the daemon, Media3 playback, `AudioManager` volume/output-device read). Still
  to do: local media folder + offline delta sync; rating/curation screens; background service;
  mDNS discovery. Authored without an Android SDK, so it needs a build pass in Android Studio.

The daemon must bind to the LAN (`harmonica serve --host 0.0.0.0`) for other devices to reach it;
give the host a DHCP reservation or use mDNS so the address is stable.
