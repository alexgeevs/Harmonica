# Harmonica

Harmonica is a music app exploring utility-maximizing recommendations while avoiding repetition.

## Current Thin Slice

- Python CLI and FastAPI daemon.
- SQLite local app database under `.harmonica/`.
- Local media scanner using embedded tags where available.
- Weighted playlist generation with song, group, and subgroup cooldowns.
- 0-5 rating factors that affect song multipliers.
- `.m3u8` export.
- React web UI for queue generation, browser playback, library editing, and settings.

## Setup

```bash
~/.local/bin/uv sync --extra dev
~/.local/bin/uv run harmonica init
```

If `uv` is not installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Backend

```bash
~/.local/bin/uv run harmonica scan --library /path/to/music
~/.local/bin/uv run harmonica generate --length 100 --output playlist.m3u8
~/.local/bin/uv run harmonica serve
```

The API defaults to `http://127.0.0.1:8765`.

## Web UI

```bash
cd web
npm install
npm run dev
```

The Vite dev server defaults to `http://127.0.0.1:5173` and proxies API calls to the backend.

## Tests

```bash
~/.local/bin/uv run pytest
~/.local/bin/uv run ruff check src/harmonica tests
cd web && npm run build
```

## Planning Notes

Direction-setting user input is preserved in `docs/planning/user-input-log.md`, and the distilled current product direction is in `docs/planning/product-direction.md`.
