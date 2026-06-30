# Per-user multi-tenancy — feature reference

How Harmonica separates users. Shipped 2026-06-30. A **user = a `DeviceConfig` profile** (named,
passphrase-protected). With no profile active the daemon runs in **legacy/local mode** —
whole-library, byte-identical to single-user behaviour (guarded by the existing test suite +
`tests/test_multitenant.py`'s no-header cases).

## What's private vs shared

| Private per profile | Shared (deduplicated pool) |
| --- | --- |
| Library membership (which songs you have) | `tracks`, `media_assets` (the physical files) |
| Playback history + stats | `weight_groups`, `rating_factors`, app defaults |
| Saved queues (`playlist_runs`) | |
| Ratings (current + history) | |
| Cover A/B verdicts + Bradley-Terry ranking | |

A **new profile starts empty** and imports its own library. On import we **dedupe-and-redirect**:
identity is resolved `song_id` → media `checksum` → `file_path`; an existing song is **linked**
(`device_config_tracks`) to the profile, never re-created or re-downloaded, and a second importer
**never mutates** the first's shared metadata/groups/assets. A profile only ever sees its own
membership, so users can't discover each other's songs or listening.

## Identity & auth

Every request carries the active profile via a header, resolved by one dependency (`get_owner` in
`api.py`):

- **`Authorization: Bearer <token>`** — a signed token (`security.issue_config_token`,
  HMAC-SHA256 over the config id with `Settings.effective_secret_key()`) issued by
  `POST /configs` and `/configs/claim` *after* the passphrase is verified. **Tamper-proof**: a
  client can't forge another profile's identity.
- **`X-Harmonica-Config-Id: <id>`** — a transitional fallback used only when no bearer token is
  present. Gives structural separation but **not** access control (any id can be named); kept so
  older clients keep working until they re-claim and pick up a token.
- **No header** → `None` → legacy/local whole-library mode.

The web client injects this once in `api.ts`'s `request()` from the stored `activeConfig`
(localStorage `harmonica.activeConfig`, which now carries the `token`). `null` profile sends nothing.

## How the scoping works (no SQLite constraint rebuilds)

- Nullable `owner_config_id` was added (additive PRAGMA, `models.ensure_additive_owner_columns`) to
  `playback_events`, `playlist_runs`, `rating_samples`, `cover_comparisons`. NULL = legacy/unowned.
- Three caches can't take an owner column (`TrackRating UNIQUE(track,factor)`,
  `CoverRenditionState.track_id` unique, `CoverSetState.sub_group` PK). Instead, **per-user state is
  derived from the append-only logs**: a profile's ratings come from its own owner-stamped
  `rating_samples` (the shared `TrackRating` cache is legacy-only), and its cover Bradley-Terry
  strengths are recomputed in-memory from its own `cover_comparisons` each time. A small additive
  `user_cover_set_state` table holds just the per-profile A/B lifecycle phase (for "settled" +
  "compare again").
- Normalisation (`normalization.py`) computes the library-wide SD/mean/calibration over the
  **owner's** samples + library; history (`history.py`) filters playback events by owner; the
  candidate pool is the owner's `device_config_tracks`. An **empty library yields an empty queue**
  (guarded — no divide-by-zero on a brand-new profile).

## Endpoints (all owner-aware)

`/tracks`, `/tracks/{id}` (404 outside your library), `/stats/summary`, `/playback-events`
(GET + POST), `/playlist-runs*`, `/queue/generate`, `/cover-sets/*`, `/cover-comparisons/next`,
`/cover-verdicts`, `/library/export-json` (your library + history only), `/library/import-json`,
`/scan` (links found/created tracks to you). `create_config`/`claim_config` return the `token`.

## Deployment note (NAS Docker)

Set `HARMONICA_MEDIA_ROOT` to the mounted media volume and `HARMONICA_SECRET_KEY` (else a random
key is generated once and persisted to `home/secret.key`). The container is the network boundary.

## Legacy data

Existing NULL-owner data stays unowned — visible only in no-header/local mode, **not** auto-assigned
to any profile (irreversible without migration tooling we don't have). To move it into a profile:
export in local mode → import under the profile (which stamps the owner).

## Tests

`tests/test_multitenant.py`: library/listening isolation, import dedupe-and-redirect, per-user
ratings, idempotent import, empty-profile queue, private saved queues, forged/missing token. Plus
the rest of the suite as the no-header golden-parity guard.
