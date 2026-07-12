# Custom Tags Design

Date: 2026-07-12. Status: approved by the owner with amendments, recorded here.

## Purpose

Harmonica has a single per-track flag, favourite. This design adds a general tag system for
organising the library. Tags are mainly organisational. A tag can also be opted in as a light
input to the queue algorithm. The feature adds system tags (Favourite, Ignored), seeded default
custom tags, user-created tags, library filtering by tag, and queue generation restricted to tags.

## Owner decisions

- Tags are mainly organisational, with an optional marginal pacing effect in both directions
  controlled by algorithm settings.
- Ignored is new. An ignored track never enters generated queues, stays visible in the library,
  and can still be played manually.
- One unified storage for favourite, ignored and custom tags. Favourite keeps its existing
  algorithm behaviour (favourite pacing) and its star in the UI exactly as they are. Other tags
  get their own UI section.
- The algorithm mechanism for custom tags is a light pacing layer. Tags never join the group
  weighting economy.
- On aggregate, carrying tags or not must not change how often a track appears relative to an
  untagged track. The pacing layer only redistributes when tagged tracks appear, not how often.
  System tags are the exception: favourite pacing changes rates deliberately and Ignored excludes.
- Each tag is either cosmetic or algorithm-active, selectable when creating or editing the tag.
- Tag definitions are shared across profiles. Assignments are per profile by default, with a
  per-tag option to make assignments shared household-wide (for example a household-made
  "without lyrics" tag that organises past the automatic fields).
- Older exports that only carry the favourite boolean keep importing through the existing
  favourite field handling. No new compatibility code is written for them.
- Keep the change light. Do not break existing behaviour. Prefer adding over modifying.

## Data model

Two new tables, additive only (persistence is `create_all`, no migrations).

`tags`: id, name (unique), kind (`system` or `custom`), shared (bool, default false),
affects_algorithm (bool, default false), created_at.

`track_tags`: id, track_id (FK), tag_id (FK), owner_config_id (nullable FK to device_configs),
created_at. Uniqueness of (track_id, tag_id, owner_config_id) is enforced in application code
because SQLite treats NULLs as distinct inside unique constraints.

Seeding runs only when the tags table is empty: system tags Favourite and Ignored, plus default
custom tags Fun, Focused, Calm, Energetic, Nostalgic and Party. Defaults are ordinary custom tags,
renamable and deletable, and deleted defaults do not come back on restart.

Backfill runs once at startup: `Track.favourite` becomes a Favourite assignment with NULL owner,
`DeviceConfigTrack.favourite` becomes a Favourite assignment owned by that config. After backfill
the tag tables are the source of truth. The favourite boolean columns stay in place and are kept
in sync on every Favourite tag change, so exports and existing code paths stay coherent.

## API

- `GET /tags` lists all tags with owner-scoped assignment counts.
- `POST /tags` creates a custom tag (name, shared, affects_algorithm).
- `PATCH /tags/{id}` renames a tag or toggles shared and affects_algorithm. System tags refuse
  all edits.
- `DELETE /tags/{id}` removes the tag and its assignments. System tags refuse.
- `TrackRead` gains a `tags` list. `PATCH /tracks/{id}` accepts it. The existing `favourite`
  boolean keeps working and maps onto the Favourite tag.
- `POST /queue/generate` gains an optional `tags` list. The candidate pool becomes tracks carrying
  any of the named tags (union), intersected with the profile scope as now.
- Ignored tracks are excluded from every generated queue at pool assembly. Manual playback and
  the library view are untouched. The queue tag picker does not offer Ignored, so the exclusion
  has no override.

## Algorithm

`TrackInput` gains the track's algorithm-active tag names. One new setting, `tag_clustering_bias`
in [-1, 1] with default 0, exposed as a real control through `GET /settings` `controls[]`.

Per selection step each algorithm-active tag contributes a small pacing factor based on how
recently that tag last played, over the same horizon the variant-family cooldown uses. Negative
bias suppresses same-tag tracks shortly after a play and compensates with a matching boost later
in the horizon (spacing). Positive bias is the mirror image (clustering).

Aggregate neutrality: the factor is zero-mean across its horizon by construction, so the
suppression and the boost cancel over time and a tagged track's overall appearance rate stays
approximately unchanged relative to an untagged one. The factor is bounded within [0.5, 1.5] even
at full bias, keeping the effect marginal. At bias 0 every factor is exactly 1.0 and queue output
is byte-identical to today, guarded by a fixed-seed parity test.

Favourite pacing is untouched and stays favourite-only. It reads the same boolean input as today,
now sourced from the Favourite tag. Cosmetic tags never reach the algorithm.

## UI

The owner asked for flexibility here and may request changes once it exists.

- Track editor: the star stays in the header. A new Tags section below the groups offers
  toggleable chips for custom tags, an Ignore toggle, and a new-tag input. Renaming, deleting and
  the shared and algorithm-active switches live in a small manage-tags view reached from that
  section.
- Library: a Tags facet group in the rail with counts (Favourites, Ignored, then customs). Search
  also matches tag names. Ignored tracks render muted so their state is visible at a glance.
- Queue: a tag picker above Generate restricts the generated queue to the picked tags. The run
  summary records the restriction.
- Settings: the tag pacing slider appears with an explanation, generated from `controls[]`.

## Multi-user

Tag definitions are global vocabulary. Assignment visibility follows one rule: for a shared tag
every assignment row counts for everyone. For a per-profile tag only rows whose owner matches the
requesting profile count, with NULL owner in local mode. Toggling shared changes visibility only,
no rows are rewritten. Counts, filters and tag-restricted queues all flow through this rule. With
no profile header and the bias slider at 0, behaviour is byte-identical to current.

## Export and import

Export gains a tags block with definitions (name, kind, shared, affects_algorithm) and
assignments. Import merges the block idempotently by name. Exports without the block import
exactly as before through the retained favourite field.

## Testing

New `tests/test_tags.py` covering: tag CRUD and system-tag protection, favourite backfill from
both columns, assignment toggle and idempotent upsert, union queue restriction, ignored exclusion
alone and combined with a profile scope, fixed-seed parity at bias 0, bias in both directions
moving same-tag spacing, a zero-mean check on the pacing factor across its horizon, owner
isolation for per-profile tags, shared-tag visibility across profiles, and an export and import
round trip. The full existing suite, ruff and the web build stay green.

## Non-goals

Tags never join group weighting. No automatic tagging. No changes to favourite pacing, ratings,
groups or variant families. The browser demo keeps working unchanged (its library has no tags and
the new setting defaults to 0).

## Follow-up

When the feature ships, consider a short paragraph on the website about organising a library
with tags.
