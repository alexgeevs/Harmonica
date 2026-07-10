# AGENTS.md — Setting Harmonica Up as a Coding Agent

Harmonica is designed to be installed and configured by an AI coding agent on the user's behalf.
This file is the provider-neutral entry point. It applies to any agent.

## Run it

```bash
uv sync                                   # install Python deps (https://astral.sh/uv if missing)
uv run harmonica serve                    # FastAPI daemon + SQLite on http://127.0.0.1:8765
cd web && npm install && npm run build    # the daemon then serves the built UI at that origin
```

That one origin, `http://localhost:8765`, is the app: build the UI once and let the daemon serve
it. The Vite dev server on port 5173 (`npm run dev`) exists only for working on the UI itself.
Do not point the user at it.

All state lives in one SQLite file under `.harmonica/`. There are no migrations: the schema is
created on first run, and new columns are added additively.

For a NAS/LAN deployment, bind with `HARMONICA_HOST=0.0.0.0` (opt-in, never the default) and use
per-user profiles with their bearer tokens. `HARMONICA_WEB_DIST` overrides where the UI is served
from.

## Import the user's library

Two routes, both idempotent:

1. **Scanner:** `POST /scan` with a folder path (or the Scan box in the Library view). Reads
   embedded tags from bare media files.
2. **Structured import:** one folder per song holding the media plus a `song_config.json`
   (title, artists, `weight_group_names` for groups, `version_family_name` for cover/rendition
   families). See `docs/agents/algorithm-and-song-fields.md` for what each field should be based
   on, and `docs/agents/classification-import-and-verify.md` for the import/verify pipeline.

Harmonica does not host, provide, or source any music. You are advised to ask the user where their
library lives and import from there.

On a shared NAS, media files are one deduplicated pool while each profile's library is private.
Import is dedupe-aware: it matches on `song_id`, then media checksum, then file path, and links a
new profile to the existing shared copy instead of importing the media again. When you set up a new
profile on a NAS that already holds other people's songs, expect this and rely on it, so the same
file is never stored twice.

## Curate and configure

- Library round-trip: `GET /library/export-json` → edit → the user reviews the proposal in the
  app's Curate view and applies each change. Nothing in the library changes until they apply.
- Settings: `GET /settings` returns real controls with explanations. `PATCH /settings` writes
  values. You can compose a preset for the user from what you know about them.
- Until most songs are rated the algorithm runs sub-optimally. Advise the Discovery preset first.

## Build on top

The whole player is a JSON API. An agent can build a custom UI for the user and plug it into the
backend. See `docs/agents/api-and-custom-ui.md` for the endpoint map and how to serve a
replacement front end.

## Private credentials

Harmonica may hold secrets that belong to the user: API keys for optional integrations, the
token-signing key, profile passphrases. These are deliberately kept outside the source tree. Do
not go looking for them, do not read or open them, and never copy their values into logs, exports,
code, or commits. If a feature needs a key, have the user enter it through the app and refer to it
by name only. You do not need its value, and you do not need to know where it lives, to do your work.

## Bugs and feedback

Report problems upstream so they can be fixed for everyone: see `CONTRIBUTING.md`. In short, open
a GitHub issue with a reproduction, or a pull request with the fix.

## Checks before proposing changes

```bash
uv run pytest -q
uv run ruff check src/harmonica tests
cd web && npm run build
```
