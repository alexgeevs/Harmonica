# Harmonica — Importing a Classification & Verifying It

> Companion to `song-classification-prompt.md`. That file tells an agent how to **produce** a
> classification payload; this file tells you how to **import** it into Harmonica and **confirm** it
> landed. Architecture rationale: `docs/planning/classification-architecture.md`.

The pipeline:

```
GET /library/export-json ──▶ classification agent ──▶ payload.json
        (current state)         (the prompt file)          │
                                                            ▼
                                   owner reviews the "Venn" map, edits payload
                                                            │
                                          back up the DB    ▼
                                                     import  ─────▶  verify  ─────▶ done
```

---

## 0. Prerequisites

- The daemon and DB exist (`.harmonica/harmonica.db`). Runner: `~/.local/bin/uv run harmonica ...`
  (in this sandbox, `.venv/bin/harmonica ...`).
- Work on a **backup** of the DB for anything that writes (Step 3). Classification is high-value and
  hard to redo; a stale-membership mistake is annoying to undo without one.

---

## 1. Export the current library

Give the agent the real current state so it can reuse existing groups and preserve `song_id`s:

```bash
curl -s http://127.0.0.1:8765/library/export-json > export.json
```

Hand `export.json` to the classification agent along with `song-classification-prompt.md`.

## 2. Run the classification agent

It returns two things (per the prompt): **`payload.json`** (the machine-readable import) and a
**review map** (the human-readable "Venn"). Do not import yet.

## 3. Owner review (the gate)

Read the review map. Confirm every **flagged-for-decision** item: each newly-invented group, each
hidden one-off, each fuzzy theme, each mood-promoted-to-group, each negative-affinity tag, each
low-confidence song. Edit `payload.json` directly to correct anything. **This is the step that
catches the Opportunity Rover class of error** — spend real attention here.

## 4. Back up the DB

```bash
cp .harmonica/harmonica.db ".harmonica/harmonica.db.bak.$(date +%Y%m%d-%H%M%S)"
```

---

## 5. Import

Pick the path that matches your situation.

### 5a. Additive import (fresh/empty library, or only ADDING classifications)

The endpoint wraps the payload in `{ "payload": … }`:

```bash
jq '{payload: .}' payload.json | \
  curl -s -X POST http://127.0.0.1:8765/library/import-json \
       -H 'content-type: application/json' --data-binary @- | jq .
```

What it writes (local/no-profile mode): each track's `artist`, `sub_group`,
`is_original_rendition`, group **memberships** (with `share`), and `cooldown_tags`. It creates any
`groups[]` it hasn't seen. Existing `assets`/`ratings` are untouched.

> **Extension fields are ignored today** — `hidden` (on groups), `reason` (on memberships),
> `cooldown_tag_meta` strengths, `confidence`, `review`. They ride along harmlessly and are consumed
> once the additive schema is built (the deferred algorithm work). Nothing is lost; they're in
> `payload.json`.

### 5b. Corrective reclassify (existing library — REMOVING songs from bad groups)

**Critical limitation:** `import-json` only **adds/updates** memberships and tags — it **never
removes** them (`serialization.py:258-280`). So importing a corrected classification over the current
polluted DB will *not* pull a song out of `Opportunity Rover`; the stale membership persists. To truly
reclassify you must **clear then import**. Use the helper (it backs up, clears memberships/tags/
`sub_group` for the payload's tracks, applies the payload via the canonical import path, and prunes
groups that end up empty):

```bash
# Stop the daemon first (SQLite: avoid two writers).
.venv/bin/python scripts/reclassify_from_payload.py payload.json            # dry-run: shows what it would do
.venv/bin/python scripts/reclassify_from_payload.py payload.json --apply    # writes (auto-backs-up first)
# Restart the daemon.
```

This is the **corrective one-off pass** (architecture doc §12.4). It's low-priority while the library
is a placeholder, but it's the correct way to fix an already-polluted DB, and it's designed so a
future agent can re-run it to correct wrong entries in place.

---

## 6. Verify the import

### 6a. Automated check (read-only)

```bash
.venv/bin/python scripts/verify_classification.py                 # audit the live DB
.venv/bin/python scripts/verify_classification.py payload.json    # also cross-check DB == payload
```

It reports and flags: group sizes (and any group > 25% of the library — an over-broad smell); songs
carrying **4+** weight groups (over-tagged); artist `share` sums that aren't ≈ 0.5 per song;
`sub_group` families that are singletons (should be `null`) or lack exactly one original; and, when a
payload is given, any track whose DB groups don't match what was classified. **Green = no flags** (or
only ones you consciously approved, e.g. a deliberate 3-group song).

### 6b. Manual spot checks

```bash
curl -s http://127.0.0.1:8765/tracks/<id> | jq '{title, artist, sub_group, groups}'
```

Pick a few known songs (a solo standalone, a collaboration, a cover, a one-off) and confirm the
groups/shares/`sub_group` read as intended.

### 6c. Re-emit the "Venn" from the live DB

Re-run the classification agent's **map-only** mode (or `verify_classification.py`'s summary) against
the *imported* state and confirm it matches the map you approved in Step 3. If the live map and the
approved map agree, the import is faithful.

---

## 7. Rollback

If anything looks wrong, restore the backup:

```bash
cp .harmonica/harmonica.db.bak.<timestamp> .harmonica/harmonica.db   # daemon stopped
```

---

## 8. Not yet wired (pending the deferred schema work)

These are captured in the payload but **not persisted** until the additive schema lands:
`WeightGroup.hidden`, signed cooldown-tag `strength` (affinity), and per-membership `reason`
provenance. Until then: hidden one-offs import as normal (visible) groups; affinity tags import as
ordinary (spacing) tags; reasons live only in `payload.json` and the review map. When that schema is
built, re-running the importer over the same `payload.json` upgrades them in place.
