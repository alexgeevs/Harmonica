# Harmonica I/O — the API, and Plugging In Your Own UI

The daemon is the product; the bundled React app is just one client. Everything the UI does goes
through the JSON API below, so an agent can build a bespoke front end for its user and serve it
from the same daemon.

Base URL: `http://127.0.0.1:8765` (or the LAN address on a NAS deployment).

## Endpoint map

| Area | Endpoints | Notes |
| --- | --- | --- |
| Health | `GET /health` | Liveness check. |
| Settings | `GET /settings`, `PATCH /settings` | `controls[]` describes every switch/slider with labels and explanations. Render these, do not hard-code. |
| Library | `GET /tracks`, `GET /tracks/{id}`, `PATCH /tracks/{id}`, `GET /groups`, `GET /rating-factors` | `PATCH /tracks` covers metadata, groups, cooldown tags, and ratings. |
| Scan | `POST /scan` | Index a folder of media within the configured media root. |
| Queue | `POST /queue/generate` | Returns a persisted run with per-item "why this song" explanations. |
| Sessions | `GET /playlist-runs`, `GET /playlist-runs/{id}`, `PATCH /playlist-runs/{id}`, `DELETE /playlist-runs/{id}`, `GET /playlist-runs/{id}/m3u8` | Saved/resumable queues. |
| Playback | `POST /playback-events`, `GET /playback-events` | Report starts, pauses, skips, completions. Skip semantics feed the algorithm. |
| Media | `GET /media/{asset_id}` | Streams a file. Serving is confined to the media root. |
| Stats | `GET /stats/summary` | Listening dashboard data. |
| Import/export | `GET /library/export-json`, `POST /library/import-json` | The agent curation round-trip. Idempotent, de-duplicating. |
| Covers | `GET /cover-sets/{sub_group}`, `POST /cover-sets/{sub_group}/reopen`, `GET /cover-comparisons/next`, `POST /cover-verdicts` | Pairwise A/B ranking of renditions. |
| Profiles | `GET /configs`, `POST /configs`, `POST /configs/claim`, `PATCH /configs/{id}` | Multi-user profiles. Create/claim returns a bearer token. |

## Authentication

Local single-user mode needs no auth. With per-user profiles, send the token returned by
`POST /configs` or `POST /configs/claim`:

```
Authorization: Bearer <token>
```

Requests without a token operate in legacy local mode on the full library. A profile's requests
see only that profile's library, ratings, history, and stats.

## Plugging in a custom UI

The daemon serves whatever static bundle you point it at, on the same origin as the API (so no
CORS concerns):

```bash
HARMONICA_WEB_DIST=/path/to/your/dist uv run harmonica serve
```

Rules of the road for a replacement front end:

- Generate queues with `POST /queue/generate` rather than picking tracks yourself. The
  anti-repetition algorithm is the product; a UI that plays tracks directly around it defeats it.
- Report playback honestly (`POST /playback-events`), including skips and completions, or the
  history-aware parts of the algorithm go blind.
- Build the settings screen from `GET /settings` `controls[]` so new knobs appear automatically.
- Media URLs come from each track's assets; stream them, do not copy them elsewhere.

API routes always take precedence over the static mount, so a custom UI cannot shadow the API.
