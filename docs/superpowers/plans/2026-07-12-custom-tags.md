# Custom Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A unified tag system (system tags Favourite and Ignored plus user-managed custom tags) with library filtering, tag-restricted queue generation, and an optional aggregate-neutral pacing layer in the algorithm.

**Architecture:** Two new additive tables (`tags`, `track_tags`) mirror the favourite per-profile pattern. Ignored tracks are excluded at candidate-pool assembly. Algorithm-active tags feed a zero-mean selection-weight factor applied in `generate_playlist`, inert at the default bias of 0. Favourite pacing and its star UI are untouched; the favourite boolean columns stay in sync with the Favourite tag on every write.

**Tech Stack:** FastAPI + SQLAlchemy (SQLite, `create_all`, additive only), pydantic schemas, React + TypeScript (Vite), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-12-custom-tags-design.md`. Read it before starting.
- **Byte parity:** with no tag assignments changed and `tag_clustering_bias` at 0, every existing behaviour (queue output for a fixed seed, exports, endpoints) must be identical to before this work.
- **Favourite pacing stays exactly as is** (`algorithm.py` lines 278–286, `favourite_pacing_enabled`/`strength`). Do not touch it.
- Persistence is `Base.metadata.create_all` — **no migrations**. New tables only; never alter existing columns.
- Settings must be **real controls** generated from `SETTING_DEFINITIONS` (`settings_store.py`), never a read-only recap.
- Preserve the colour scheme: deep green `#1b362e`, mint `#eef3f1`, teal `#206a5d`, gold `#f1c84b`.
- System tag names are exactly `"Favourite"` and `"Ignored"`. Default custom tags: `"Fun"`, `"Focused"` (owner amendment 2026-07-12: defaults must be distinct, so the starter set was cut from six to two; profile-scoped tag deletion was also added post-plan).
- Commits: short imperative messages, committed as the configured git user (`alexgeevs`), **no Co-Authored-By/agent trailer**, never `git add -A` (stage named files only; leave `uv.lock` and `$HOME` dotfiles alone). **Never push.**
- Test/lint commands: `~/.local/bin/uv run pytest -q`, `~/.local/bin/uv run ruff check src/harmonica tests`, `cd web && npm run build`. If the uv cache is read-only in a sandbox, use `.venv/bin/python -m pytest -q` and `.venv/bin/python -m ruff check src/harmonica tests`.
- Do not kill any daemon already running on port 8765.
- Ruff line length is 100. Match existing comment density and docstring style.

---

### Task 1: Data model — tags tables, seeding, backfill, visibility helpers

**Files:**
- Modify: `src/harmonica/models.py` (new models after `TrackCooldownTag`, helpers at end of file)
- Modify: `src/harmonica/db.py:36` (wire seeding into `init_db`)
- Test: `tests/test_tags.py` (new file)

**Interfaces:**
- Produces: models `Tag` (fields `id`, `name`, `kind`, `shared`, `affects_algorithm`, `created_at`) and `TrackTag` (fields `id`, `track_id`, `tag_id`, `owner_config_id`, `created_at`).
- Produces: constants `FAVOURITE_TAG_NAME = "Favourite"`, `IGNORED_TAG_NAME = "Ignored"`, `SYSTEM_TAG_NAMES`, `DEFAULT_CUSTOM_TAG_NAMES`.
- Produces: functions `seed_and_backfill_tags(engine) -> None`, `visible_tag_rows(session, owner_config_id) -> list[tuple[int, Tag]]`, `visible_tags_by_track(session, owner_config_id) -> dict[int, list[str]]`, `tag_track_ids(session, tag_names, owner_config_id) -> set[int]`, `algorithm_tag_inputs(session, owner_config_id) -> tuple[set[int], dict[int, frozenset[str]]]`, `set_favourite_tag(session, track_id, value, owner_config_id) -> None`. All in `harmonica.models`.

- [x] **Step 1: Write the failing tests**

Create `tests/test_tags.py`:

```python
"""Unified tags: system tags (Favourite, Ignored), starter custom tags, per-profile and shared
assignments, tag-restricted queues, and the light zero-mean pacing layer."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from harmonica.api import create_app
from harmonica.db import SessionLocal, engine, init_db
from harmonica.models import (
    DEFAULT_CUSTOM_TAG_NAMES,
    FAVOURITE_TAG_NAME,
    IGNORED_TAG_NAME,
    DeviceConfig,
    DeviceConfigTrack,
    Tag,
    Track,
    TrackTag,
    seed_and_backfill_tags,
    visible_tags_by_track,
)
from harmonica.security import hash_passphrase


def test_seed_creates_system_and_starter_tags() -> None:
    init_db()
    with SessionLocal() as session:
        by_name = {tag.name: tag for tag in session.scalars(select(Tag))}
    assert by_name[FAVOURITE_TAG_NAME].kind == "system"
    assert by_name[IGNORED_TAG_NAME].kind == "system"
    for name in DEFAULT_CUSTOM_TAG_NAMES:
        assert by_name[name].kind == "custom"
        assert by_name[name].shared is False
        assert by_name[name].affects_algorithm is False


def test_seed_is_idempotent_and_does_not_resurrect_deleted_defaults() -> None:
    init_db()
    with SessionLocal() as session:
        tag = session.scalar(select(Tag).where(Tag.name == "Party"))
        if tag is not None:
            session.delete(tag)
            session.commit()
    seed_and_backfill_tags(engine)
    with SessionLocal() as session:
        assert session.scalar(select(Tag).where(Tag.name == "Party")) is None


def test_backfill_copies_both_favourite_columns() -> None:
    init_db()
    with SessionLocal() as session:
        track = Track(song_id="tags_backfill_1", title="Backfill", favourite=True)
        session.add(track)
        config = DeviceConfig(name="tags-backfill", passphrase_hash=hash_passphrase("pw"))
        session.add(config)
        session.flush()
        session.add(
            DeviceConfigTrack(config_id=config.id, track_id=track.id, favourite=True)
        )
        # Force a re-run of the one-time pass by clearing the tags tables.
        session.execute(delete(TrackTag))
        session.execute(delete(Tag))
        session.commit()
        track_id, config_id = track.id, config.id
    seed_and_backfill_tags(engine)
    with SessionLocal() as session:
        local_tags = visible_tags_by_track(session, None)
        owned_tags = visible_tags_by_track(session, config_id)
    assert FAVOURITE_TAG_NAME in local_tags.get(track_id, [])
    assert FAVOURITE_TAG_NAME in owned_tags.get(track_id, [])
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: FAIL with `ImportError` (cannot import `Tag` etc. from `harmonica.models`).

- [x] **Step 3: Add the models and constants**

In `src/harmonica/models.py`, directly after the `TrackCooldownTag` class (line 166), insert:

```python
FAVOURITE_TAG_NAME = "Favourite"
IGNORED_TAG_NAME = "Ignored"
SYSTEM_TAG_NAMES = (FAVOURITE_TAG_NAME, IGNORED_TAG_NAME)
DEFAULT_CUSTOM_TAG_NAMES = ("Fun", "Focused", "Calm", "Energetic", "Nostalgic", "Party")


class Tag(Base):
    """A user-facing organisational label on tracks. ``kind`` separates the fixed system tags
    (Favourite, Ignored) from user-managed custom tags. ``shared`` makes ASSIGNMENTS
    household-wide (stored unowned) instead of per-profile. ``affects_algorithm`` opts a tag into
    the light pacing layer (cosmetic otherwise). Distinct from ``CooldownTag``, which is the
    scanner's grouping shorthand, not a user tag."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="custom")  # 'system' | 'custom'
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    affects_algorithm: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class TrackTag(Base):
    """One tag assignment. ``owner_config_id`` scopes it: a profile's private opinion, or NULL for
    local mode and for every assignment of a shared tag. No UNIQUE constraint because SQLite
    treats NULLs as distinct inside one; uniqueness of (track, tag, owner) is enforced by the
    idempotent upserts in the API and import layers."""

    __tablename__ = "track_tags"
    __table_args__ = (Index("ix_track_tags_tag_owner", "tag_id", "owner_config_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), index=True)
    owner_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_configs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    tag: Mapped[Tag] = relationship()
```

- [x] **Step 4: Add the seeding/backfill and visibility helpers**

At the end of `src/harmonica/models.py` (after `ensure_additive_owner_columns`), add:

```python
def seed_and_backfill_tags(engine: Engine) -> None:
    """One-time, idempotent: create the system tags (Favourite, Ignored) and the starter custom
    tags, then copy the existing favourite booleans into tag assignments (``Track.favourite`` →
    an unowned row; ``DeviceConfigTrack.favourite`` → a row owned by that profile). No-op once
    any tag exists, so renamed or deleted starter tags never come back."""
    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(Tag)):
            return
        by_name: dict[str, Tag] = {}
        for name in SYSTEM_TAG_NAMES:
            tag = Tag(name=name, kind="system")
            session.add(tag)
            by_name[name] = tag
        for name in DEFAULT_CUSTOM_TAG_NAMES:
            session.add(Tag(name=name, kind="custom"))
        session.flush()
        favourite = by_name[FAVOURITE_TAG_NAME]
        for track_id in session.scalars(select(Track.id).where(Track.favourite.is_(True))):
            session.add(TrackTag(track_id=track_id, tag_id=favourite.id, owner_config_id=None))
        rows = session.execute(
            select(DeviceConfigTrack.track_id, DeviceConfigTrack.config_id).where(
                DeviceConfigTrack.favourite.is_(True)
            )
        ).all()
        for track_id, config_id in rows:
            session.add(
                TrackTag(track_id=track_id, tag_id=favourite.id, owner_config_id=config_id)
            )
        session.commit()


def visible_tag_rows(session: Session, owner_config_id: int | None) -> list[tuple[int, Tag]]:
    """Every (track_id, Tag) assignment visible to one scope. A shared tag's assignments count
    for everyone; a per-profile tag counts only rows stamped with the requesting owner (NULL in
    local mode)."""
    rows = session.execute(
        select(TrackTag.track_id, TrackTag.owner_config_id, Tag).join(
            Tag, TrackTag.tag_id == Tag.id
        )
    ).all()
    return [
        (track_id, tag)
        for track_id, row_owner, tag in rows
        if tag.shared or row_owner == owner_config_id
    ]


def visible_tags_by_track(session: Session, owner_config_id: int | None) -> dict[int, list[str]]:
    """Tag names per track for one scope, sorted for stable API output."""
    result: dict[int, list[str]] = {}
    for track_id, tag in visible_tag_rows(session, owner_config_id):
        names = result.setdefault(track_id, [])
        if tag.name not in names:
            names.append(tag.name)
    for names in result.values():
        names.sort()
    return result


def tag_track_ids(
    session: Session, tag_names: list[str], owner_config_id: int | None
) -> set[int]:
    """Union of track ids carrying ANY of the named tags, in one scope."""
    wanted = set(tag_names)
    return {
        track_id
        for track_id, tag in visible_tag_rows(session, owner_config_id)
        if tag.name in wanted
    }


def algorithm_tag_inputs(
    session: Session, owner_config_id: int | None
) -> tuple[set[int], dict[int, frozenset[str]]]:
    """What queue generation needs from the tags in one scope: the ignored track ids (always
    excluded from the candidate pool) and each track's algorithm-active tag names (fed to the
    light pacing layer). Favourite stays out of both — its algorithm effect is favourite pacing,
    driven by the existing boolean input."""
    ignored: set[int] = set()
    active: dict[int, set[str]] = {}
    for track_id, tag in visible_tag_rows(session, owner_config_id):
        if tag.name == IGNORED_TAG_NAME:
            ignored.add(track_id)
        elif tag.affects_algorithm:
            active.setdefault(track_id, set()).add(tag.name)
    return ignored, {track_id: frozenset(names) for track_id, names in active.items()}


def set_favourite_tag(
    session: Session, track_id: int, value: bool, owner_config_id: int | None
) -> None:
    """Keep the Favourite tag row in step with the favourite boolean for one scope (the tag
    tables are the source of truth, but both systems must agree on every write)."""
    tag = session.scalar(select(Tag).where(Tag.name == FAVOURITE_TAG_NAME))
    if tag is None:
        return
    owner_clause = (
        TrackTag.owner_config_id.is_(None)
        if owner_config_id is None
        else TrackTag.owner_config_id == owner_config_id
    )
    row = session.scalar(
        select(TrackTag).where(
            TrackTag.track_id == track_id, TrackTag.tag_id == tag.id, owner_clause
        )
    )
    if value and row is None:
        session.add(TrackTag(track_id=track_id, tag_id=tag.id, owner_config_id=owner_config_id))
    elif not value and row is not None:
        session.delete(row)
```

- [x] **Step 5: Wire seeding into init_db**

In `src/harmonica/db.py`, after `models.backfill_rating_samples(engine)` (line 36), add:

```python
    models.seed_and_backfill_tags(engine)
```

- [x] **Step 6: Run the tests**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: 3 passed.

- [x] **Step 7: Run the full suite and ruff (parity guard)**

Run: `~/.local/bin/uv run pytest -q && ~/.local/bin/uv run ruff check src/harmonica tests`
Expected: all pass, no lint errors.

- [x] **Step 8: Commit**

```bash
git add src/harmonica/models.py src/harmonica/db.py tests/test_tags.py
git commit -m "Add unified tags data model with seeding and favourite backfill"
```

---

### Task 2: Tag CRUD API

**Files:**
- Modify: `src/harmonica/schemas.py` (after `TrackUpdate`, line 108)
- Modify: `src/harmonica/api.py` (imports; endpoints before the `# --- Device configs` section at line 817; helper after `rating_factor_to_schema`)
- Test: `tests/test_tags.py`

**Interfaces:**
- Consumes: `Tag`, `TrackTag`, `SYSTEM_TAG_NAMES`, `visible_tag_rows` from Task 1.
- Produces: schemas `TagRead` (`id`, `name`, `kind`, `shared`, `affects_algorithm`, `track_count`), `TagCreate` (`name`, `shared=False`, `affects_algorithm=False`), `TagUpdate` (all optional). Endpoints `GET /tags`, `POST /tags`, `PATCH /tags/{tag_id}`, `DELETE /tags/{tag_id}`. Helper `tag_to_schema(tag, track_count) -> TagRead`.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_tags.py`:

```python
def test_tag_crud_and_system_protection() -> None:
    with TestClient(create_app()) as client:
        listed = client.get("/tags").json()
        names = {entry["name"] for entry in listed}
        assert {FAVOURITE_TAG_NAME, IGNORED_TAG_NAME, "Fun", "Focused"} <= names

        created = client.post(
            "/tags", json={"name": "Workout", "shared": False, "affects_algorithm": True}
        )
        assert created.status_code == 200
        tag = created.json()
        assert tag["kind"] == "custom" and tag["affects_algorithm"] is True

        assert client.post("/tags", json={"name": "Workout"}).status_code == 409

        renamed = client.patch(f"/tags/{tag['id']}", json={"name": "Gym", "shared": True})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Gym" and renamed.json()["shared"] is True

        assert client.delete(f"/tags/{tag['id']}").status_code == 204
        assert "Gym" not in {entry["name"] for entry in client.get("/tags").json()}

        system_id = next(
            entry["id"] for entry in listed if entry["name"] == FAVOURITE_TAG_NAME
        )
        assert client.patch(f"/tags/{system_id}", json={"name": "X"}).status_code == 403
        assert client.delete(f"/tags/{system_id}").status_code == 403


def test_deleting_a_tag_removes_its_assignments() -> None:
    with TestClient(create_app()) as client:
        client.post("/tags", json={"name": "Doomed"})
        with SessionLocal() as session:
            track = Track(song_id="tags_doomed_1", title="Doomed carrier")
            session.add(track)
            doomed = session.scalar(select(Tag).where(Tag.name == "Doomed"))
            session.flush()
            session.add(TrackTag(track_id=track.id, tag_id=doomed.id, owner_config_id=None))
            session.commit()
            tag_id, track_id = doomed.id, track.id
        assert client.delete(f"/tags/{tag_id}").status_code == 204
        with SessionLocal() as session:
            remaining = session.scalars(
                select(TrackTag).where(TrackTag.track_id == track_id)
            ).all()
        assert remaining == []
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: the two new tests FAIL with 404s (`/tags` does not exist).

- [x] **Step 3: Add the schemas**

In `src/harmonica/schemas.py`, after `TrackUpdate` (line 108), add:

```python
class TagRead(BaseModel):
    id: int
    name: str
    kind: str
    shared: bool
    affects_algorithm: bool
    track_count: int = 0


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    shared: bool = False
    affects_algorithm: bool = False


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    shared: bool | None = None
    affects_algorithm: bool | None = None
```

- [x] **Step 4: Add the endpoints**

In `src/harmonica/api.py`:

1. Extend the `harmonica.models` import block (line 23) with `Tag`, `TrackTag`, `visible_tag_rows`, and the `harmonica.schemas` import block (line 46) with `TagCreate`, `TagRead`, `TagUpdate`.
2. Before the `# --- Device configs` comment (line 817), add:

```python
    # --- Tags (organisational labels; system tags Favourite/Ignored are fixed) ---

    @app.get("/tags", response_model=list[TagRead])
    def list_tags(session: SessionDep, owner: OwnerDep) -> list[TagRead]:
        counts: dict[int, set[int]] = {}
        for track_id, tag in visible_tag_rows(session, owner.id if owner else None):
            counts.setdefault(tag.id, set()).add(track_id)
        tags = session.scalars(select(Tag).order_by(Tag.kind.desc(), Tag.name)).all()
        return [tag_to_schema(tag, len(counts.get(tag.id, ()))) for tag in tags]

    @app.post("/tags", response_model=TagRead)
    def create_tag(payload: TagCreate, session: SessionDep) -> TagRead:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Tag name cannot be empty")
        if session.scalar(select(Tag).where(Tag.name == name)):
            raise HTTPException(status_code=409, detail="A tag with that name already exists")
        tag = Tag(
            name=name,
            kind="custom",
            shared=payload.shared,
            affects_algorithm=payload.affects_algorithm,
        )
        session.add(tag)
        session.commit()
        return tag_to_schema(tag, 0)

    @app.patch("/tags/{tag_id}", response_model=TagRead)
    def update_tag(
        tag_id: int, payload: TagUpdate, session: SessionDep, owner: OwnerDep
    ) -> TagRead:
        tag = session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        if tag.kind == "system":
            raise HTTPException(status_code=403, detail="System tags cannot be edited")
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="Tag name cannot be empty")
            clash = session.scalar(select(Tag).where(Tag.name == name, Tag.id != tag.id))
            if clash is not None:
                raise HTTPException(
                    status_code=409, detail="A tag with that name already exists"
                )
            tag.name = name
        if payload.shared is not None:
            # Visibility flips only; existing assignment rows are never rewritten.
            tag.shared = payload.shared
        if payload.affects_algorithm is not None:
            tag.affects_algorithm = payload.affects_algorithm
        session.commit()
        count = len(
            {
                track_id
                for track_id, visible in visible_tag_rows(
                    session, owner.id if owner else None
                )
                if visible.id == tag.id
            }
        )
        return tag_to_schema(tag, count)

    @app.delete("/tags/{tag_id}", status_code=204)
    def delete_tag(tag_id: int, session: SessionDep) -> Response:
        tag = session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        if tag.kind == "system":
            raise HTTPException(status_code=403, detail="System tags cannot be deleted")
        # Explicit: SQLite FK cascades are not enforced through this connection.
        session.execute(delete(TrackTag).where(TrackTag.tag_id == tag.id))
        session.delete(tag)
        session.commit()
        return Response(status_code=204)
```

3. After `rating_factor_to_schema` (line 1098), add the module-level helper:

```python
def tag_to_schema(tag: Tag, track_count: int) -> TagRead:
    return TagRead(
        id=tag.id,
        name=tag.name,
        kind=tag.kind,
        shared=tag.shared,
        affects_algorithm=tag.affects_algorithm,
        track_count=track_count,
    )
```

- [x] **Step 5: Run the tests**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/harmonica/schemas.py src/harmonica/api.py tests/test_tags.py
git commit -m "Add tag CRUD endpoints with system-tag protection"
```

---

### Task 3: Tags on tracks — read, write, favourite sync, owner scoping

**Files:**
- Modify: `src/harmonica/schemas.py` (`TrackRead` line 63, `TrackUpdate` line 90)
- Modify: `src/harmonica/api.py` (`track_to_schema` line 1009, `apply_track_update` line 1118, `list_tracks` line 498, `read_track` line 515, `update_track` line 529; new helper `replace_track_tags`)
- Test: `tests/test_tags.py`

**Interfaces:**
- Consumes: `set_favourite_tag`, `visible_tags_by_track`, `FAVOURITE_TAG_NAME` from Task 1.
- Produces: `TrackRead.tags: list[str]`; `TrackUpdate.tags: list[str] | None`; `track_to_schema(track, ratings_average, favourite, tags)` (new keyword `tags: list[str] | None = None`); `replace_track_tags(session, track, tag_names, owner_config_id)`.
- Write semantics: the `tags` list REPLACES the assignments this scope may touch. A shared tag's rows are stored unowned (any profile may add or remove them — household-editable); a per-profile tag's rows are stamped with the requester and never touch another profile's rows. Unknown names are auto-created as cosmetic per-profile custom tags (the same forgiving idiom as `replace_groups`). If both `favourite` and `tags` appear in one PATCH, the `tags` list wins (it is applied last and syncs the boolean).

- [x] **Step 1: Write the failing tests**

Append to `tests/test_tags.py`:

```python
def _seed_track(song_id: str, title: str) -> int:
    with SessionLocal() as session:
        track = Track(song_id=song_id, title=title)
        session.add(track)
        session.commit()
        return track.id


def _make_profile(client: TestClient, name: str) -> tuple[int, str]:
    created = client.post(
        "/configs", json={"name": name, "passphrase": "pw-" + name, "track_ids": []}
    )
    if created.status_code == 409:
        created = client.post("/configs/claim", json={"name": name, "passphrase": "pw-" + name})
    body = created.json()
    return body["id"], body["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_track_tags_roundtrip_and_favourite_sync() -> None:
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_rt_1", "Roundtrip")
        saved = client.patch(
            f"/tracks/{track_id}", json={"tags": ["Fun", "Brand New", FAVOURITE_TAG_NAME]}
        )
        assert saved.status_code == 200
        body = saved.json()
        assert set(body["tags"]) == {"Fun", "Brand New", FAVOURITE_TAG_NAME}
        assert body["favourite"] is True  # tag write synced the boolean
        with SessionLocal() as session:
            assert session.get(Track, track_id).favourite is True
            created = session.scalar(select(Tag).where(Tag.name == "Brand New"))
            assert created is not None and created.kind == "custom"

        # Removing Favourite from the list clears the boolean too.
        cleared = client.patch(f"/tracks/{track_id}", json={"tags": ["Fun"]}).json()
        assert cleared["favourite"] is False and cleared["tags"] == ["Fun"]

        # The reverse direction: the plain favourite boolean writes the tag row.
        starred = client.patch(f"/tracks/{track_id}", json={"favourite": True}).json()
        assert FAVOURITE_TAG_NAME in starred["tags"]


def test_per_profile_tags_are_private_and_shared_tags_are_household() -> None:
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_scope_1", "Scoped")
        id_a, token_a = _make_profile(client, "tags-alice")
        _, token_b = _make_profile(client, "tags-bob")
        # Both profiles need the track in their library to see it at all.
        for token in (token_a, token_b):
            client.post(
                "/library/import-json",
                json={"payload": {"tracks": [{"song_id": "tags_scope_1", "title": "Scoped"}]}},
                headers=_auth(token),
            )
        client.post("/tags", json={"name": "No Lyrics", "shared": True})

        client.patch(
            f"/tracks/{track_id}",
            json={"tags": ["Fun", "No Lyrics"]},
            headers=_auth(token_a),
        )
        seen_by_a = client.get(f"/tracks/{track_id}", headers=_auth(token_a)).json()["tags"]
        seen_by_b = client.get(f"/tracks/{track_id}", headers=_auth(token_b)).json()["tags"]
        assert set(seen_by_a) == {"Fun", "No Lyrics"}
        assert seen_by_b == ["No Lyrics"]  # A's per-profile Fun is private; shared is not

        # B removes the shared assignment for the whole household, never A's private one.
        client.patch(f"/tracks/{track_id}", json={"tags": []}, headers=_auth(token_b))
        assert client.get(f"/tracks/{track_id}", headers=_auth(token_a)).json()["tags"] == [
            "Fun"
        ]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: the two new tests FAIL (`tags` key missing / ignored by PATCH).

- [x] **Step 3: Extend the schemas**

In `src/harmonica/schemas.py`:
- `TrackRead`: after `cooldown_tags` (line 80), add `tags: list[str] = Field(default_factory=list)`.
- `TrackUpdate`: after `cooldown_tags` (line 104), add `tags: list[str] | None = Field(default=None, max_length=100)`.

- [x] **Step 4: Thread tags through the API**

In `src/harmonica/api.py`:

1. Extend the models import with `set_favourite_tag`, `visible_tags_by_track`, `FAVOURITE_TAG_NAME`.
2. `track_to_schema` (line 1009): add parameter `tags: list[str] | None = None` and pass `tags=tags or []` into the `TrackRead(...)` call. (Queue-item and comparison snapshots keep the default empty list — the library is the tags surface.)
3. `list_tracks` (line 498): before the return, add `tags_map = visible_tags_by_track(session, owner.id if owner else None)` and pass `tags=tags_map.get(track.id)` into `track_to_schema`.
4. `read_track` and the reload at the end of `update_track`: pass `tags=visible_tags_by_track(session, owner.id if owner else None).get(track_id)`.
5. `apply_track_update` (line 1118): after the existing favourite handling and before the ratings block, add:

```python
    if payload.tags is None and "favourite" in fields:
        # A favourite-only write (older clients, curation flows) still keeps the tag in step.
        set_favourite_tag(session, track.id, bool(fields["favourite"]), owner_config_id)
    if payload.tags is not None:
        replace_track_tags(session, track, payload.tags, owner_config_id)
```

6. After `replace_tags` (line 1226), add:

```python
def replace_track_tags(
    session: Session, track: Track, tag_names: list[str], owner_config_id: int | None
) -> None:
    """Replace the track's tag assignments this scope may touch. A shared tag's rows are stored
    unowned (household-editable by any profile); a per-profile tag's rows are stamped with the
    requester and never touch another profile's rows. Unknown names become cosmetic per-profile
    custom tags. The favourite boolean columns are kept in step so the algorithm and exports
    keep working unchanged."""
    wanted: list[str] = []
    seen: set[str] = set()
    for name in tag_names:
        cleaned = name.strip()[:120]
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            wanted.append(cleaned)
    tags_by_name = {tag.name: tag for tag in session.scalars(select(Tag))}
    for name in wanted:
        if name not in tags_by_name:
            tag = Tag(name=name, kind="custom")
            session.add(tag)
            session.flush()
            tags_by_name[name] = tag
    tag_by_id = {tag.id: tag for tag in tags_by_name.values()}
    rows = session.scalars(select(TrackTag).where(TrackTag.track_id == track.id)).all()
    existing: set[tuple[int, int | None]] = set()
    for row in rows:
        tag = tag_by_id.get(row.tag_id)
        if tag is None:
            continue
        expected_owner = None if tag.shared else owner_config_id
        if row.owner_config_id != expected_owner:
            continue  # another scope's row — never touched
        if tag.name in seen:
            existing.add((row.tag_id, row.owner_config_id))
        else:
            session.delete(row)
    for name in wanted:
        tag = tags_by_name[name]
        row_owner = None if tag.shared else owner_config_id
        if (tag.id, row_owner) not in existing:
            session.add(
                TrackTag(track_id=track.id, tag_id=tag.id, owner_config_id=row_owner)
            )
    favourite = FAVOURITE_TAG_NAME in seen
    if owner_config_id is None:
        track.favourite = favourite
    else:
        set_owner_favourite(session, owner_config_id, track.id, favourite)
```

- [x] **Step 5: Run the tests, full suite, ruff**

Run: `~/.local/bin/uv run pytest -q && ~/.local/bin/uv run ruff check src/harmonica tests`
Expected: all pass (existing suites confirm parity).

- [x] **Step 6: Commit**

```bash
git add src/harmonica/schemas.py src/harmonica/api.py tests/test_tags.py
git commit -m "Thread tags through track read and update with favourite sync"
```

---

### Task 4: Queue integration — ignored exclusion and tag-restricted generation

**Files:**
- Modify: `src/harmonica/playlist.py` (`load_algorithm_inputs` line 51, `generate_and_persist_playlist` line 243)
- Modify: `src/harmonica/schemas.py` (`QueueGenerateRequest` line 122)
- Modify: `src/harmonica/api.py` (`generate_queue` line 578)
- Test: `tests/test_tags.py`

**Interfaces:**
- Consumes: `algorithm_tag_inputs`, `tag_track_ids`, `IGNORED_TAG_NAME` from Task 1.
- Produces: `QueueGenerateRequest.tags: list[str] | None`; `generate_and_persist_playlist(..., queue_tags: list[str] | None = None)` which stamps `{"queue_tags": [...]}` into the run's `settings_json` when set.
- Semantics: ignored tracks never enter the candidate pool (any scope, any request). A `tags` list restricts the pool to the union of the named tags' tracks, intersected with the profile scope; `"Ignored"` in the list is dropped server-side; unknown names contribute nothing (an all-unknown list yields an empty run, not an error).

- [x] **Step 1: Write the failing tests**

Append to `tests/test_tags.py`:

```python
def _run_track_ids(client: TestClient, seed: str, tags: list[str] | None = None) -> list[int]:
    body: dict = {"length": 12, "seed": seed, "explain": False, "ui_active": False}
    if tags is not None:
        body["tags"] = tags
    run = client.post("/queue/generate", json=body)
    assert run.status_code == 200
    return [item["track"]["id"] for item in run.json()["items"]]


def test_ignored_tracks_never_enter_generated_queues() -> None:
    # Deterministic pool: restrict generation to one unique tag carried by kept + dropped,
    # so the assertion cannot flake against tracks other test files seeded into the shared DB.
    # This also proves ignored wins over an explicit tag restriction.
    with TestClient(create_app()) as client:
        kept = [_seed_track(f"tags_ign_keep_{i}", f"Keep {i}") for i in range(3)]
        dropped = _seed_track("tags_ign_drop", "Dropped")
        for track_id in kept:
            client.patch(f"/tracks/{track_id}", json={"tags": ["Ignore Pool"]})
        client.patch(f"/tracks/{dropped}", json={"tags": ["Ignore Pool", IGNORED_TAG_NAME]})
        played = set(_run_track_ids(client, seed="ignored-seed", tags=["Ignore Pool"]))
        assert dropped not in played
        assert played and played <= set(kept)


def test_ignored_is_profile_scoped_and_excluded_for_that_profile() -> None:
    # Bob ignores a shared song: it vanishes from HIS generated queues only. Alice's view and
    # queues are untouched, because Ignored assignments are per-profile like favourites.
    with TestClient(create_app()) as client:
        _, token_a = _make_profile(client, "tags-ign-alice")
        _, token_b = _make_profile(client, "tags-ign-bob")
        payload = {
            "tracks": [
                {"song_id": f"tags_pign_{i}", "title": f"Shared {i}"} for i in range(3)
            ]
        }
        for token in (token_a, token_b):
            client.post("/library/import-json", json={"payload": payload}, headers=_auth(token))
        with SessionLocal() as session:
            target = session.scalar(
                select(Track.id).where(Track.song_id == "tags_pign_0")
            )
        client.patch(
            f"/tracks/{target}", json={"tags": [IGNORED_TAG_NAME]}, headers=_auth(token_b)
        )

        def owned_run(token: str) -> set[int]:
            run = client.post(
                "/queue/generate",
                json={"length": 30, "seed": "pign", "explain": False, "ui_active": False},
                headers=_auth(token),
            )
            assert run.status_code == 200
            return {item["track"]["id"] for item in run.json()["items"]}

        assert target not in owned_run(token_b)
        assert target in owned_run(token_a)
        assert IGNORED_TAG_NAME not in client.get(
            f"/tracks/{target}", headers=_auth(token_a)
        ).json()["tags"]


def test_queue_restricted_to_tag_union() -> None:
    with TestClient(create_app()) as client:
        fun = [_seed_track(f"tags_union_fun_{i}", f"Fun {i}") for i in range(2)]
        calm = _seed_track("tags_union_calm", "Calm one")
        other = _seed_track("tags_union_other", "Untagged")
        for track_id in fun:
            client.patch(f"/tracks/{track_id}", json={"tags": ["Fun"]})
        client.patch(f"/tracks/{calm}", json={"tags": ["Calm"]})
        played = set(_run_track_ids(client, seed="union-seed", tags=["Fun", "Calm"]))
        assert played <= set(fun) | {calm}
        assert other not in played
        only_fun = set(_run_track_ids(client, seed="union-seed", tags=["Fun"]))
        assert only_fun <= set(fun)


def test_unknown_tag_restriction_yields_empty_run() -> None:
    with TestClient(create_app()) as client:
        _seed_track("tags_unknown_1", "Present")
        assert _run_track_ids(client, seed="s", tags=["No Such Tag"]) == []
```

Note: these tests share one suite-wide DB, so restriction assertions use subset checks against the tracks they created, never exact library counts.

- [x] **Step 2: Run the tests to verify they fail**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: all four new tests FAIL — the unknown `tags` body key is ignored by the current schema, so runs draw from the whole library, and ignored tracks still appear.

- [x] **Step 3: Exclude ignored tracks at pool assembly**

In `src/harmonica/playlist.py`:
1. Extend the models import (line 27) with `algorithm_tag_inputs`.
2. In `load_algorithm_inputs`, directly after the `tracks = (...)` included-filter statement (line 69-73), add:

```python
    # Ignored is a hard exclusion from every generated queue (manual playback and the library
    # view are untouched). Applied before normalisation so the owner's calibration pool matches
    # what can actually play.
    ignored_ids, active_tag_names = algorithm_tag_inputs(session, owner_config_id)
    if ignored_ids:
        tracks = [track for track in tracks if track.id not in ignored_ids]
```

(`active_tag_names` is consumed in Task 5; keeping the single call here avoids a second table scan.)

- [x] **Step 4: Accept a tags restriction on generation**

1. `src/harmonica/schemas.py`, `QueueGenerateRequest` (line 122): add field

```python
    tags: list[str] | None = Field(default=None, max_length=50)
```

2. `src/harmonica/api.py`, extend the models import with `tag_track_ids` and `IGNORED_TAG_NAME`. In `generate_queue` (line 578), after the `if config is not None:` block and before the `generate_and_persist_playlist` call, add:

```python
        requested_tags = [
            name.strip()
            for name in (payload.tags or [])
            if name.strip() and name.strip() != IGNORED_TAG_NAME
        ]
        if requested_tags:
            # Union: a track carrying ANY requested tag qualifies; intersected with the
            # profile's library. Unknown names contribute nothing (an empty pool = empty run).
            tag_pool = tag_track_ids(session, requested_tags, owner.id if owner else None)
            included_track_ids = (
                tag_pool if included_track_ids is None else included_track_ids & tag_pool
            )
```

and pass `queue_tags=requested_tags or None` into the `generate_and_persist_playlist(...)` call.

3. `src/harmonica/playlist.py`, `generate_and_persist_playlist` (line 243): add parameter `queue_tags: list[str] | None = None` and change the `PlaylistRun(...)` construction to record the restriction:

```python
    snapshot = settings_snapshot(settings)
    if queue_tags:
        snapshot["queue_tags"] = list(queue_tags)
    run = PlaylistRun(
        seed=str(seed) if seed is not None else None,
        length=length,
        settings_json=json.dumps(snapshot),
        owner_config_id=owner_config_id,
    )
```

- [x] **Step 5: Run the tests, full suite, ruff**

Run: `~/.local/bin/uv run pytest -q && ~/.local/bin/uv run ruff check src/harmonica tests`
Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/harmonica/playlist.py src/harmonica/schemas.py src/harmonica/api.py tests/test_tags.py
git commit -m "Exclude ignored tracks from queues and add tag-restricted generation"
```

---

### Task 5: Algorithm — light zero-mean tag pacing layer

**Files:**
- Modify: `src/harmonica/config.py` (after `group_clustering_bias`, line 87)
- Modify: `src/harmonica/settings_store.py` (after the `group_clustering_bias` definition, line 209)
- Modify: `src/harmonica/schemas.py` (`SettingsRead`, after `group_clustering_bias` line 192)
- Modify: `src/harmonica/algorithm.py` (`AlgorithmTrack` line 52, new functions after `apply_clustering_bias` line 177, `generate_playlist` loop)
- Modify: `src/harmonica/playlist.py` (`load_algorithm_inputs` — thread tags into `AlgorithmTrack`; `settings_snapshot` line 333)
- Modify: `site/demo/py/driver.py` (Settings stub, line 72)
- Test: `tests/test_tags.py`

**Interfaces:**
- Consumes: `active_tag_names` dict from Task 3's `algorithm_tag_inputs` call site in `load_algorithm_inputs`.
- Produces: `Settings.tag_clustering_bias: float = 0.0`; `AlgorithmTrack.tags: frozenset[str] = frozenset()`; `tag_pacing_factor(distance, horizon, bias) -> float`; `apply_tag_pacing(tracks, scores, current_index, tag_last_played, settings) -> list[float]`.
- The factor: for a tag last played `d` steps ago with horizon `h = min(30, max(len(tracks), 1))`, `factor = 1 + bias * (0.5 - d / h)` for `1 <= d <= h - 1`, else `1.0`. Mean proximity over `d = 1..h-1` is exactly 0.5, so the factor is zero-mean across the horizon — the aggregate appearance rate of tagged tracks is preserved while their timing shifts. Bounded in (0.5, 1.5) at full bias. Positive bias boosts near a recent same-tag play (clustering); negative suppresses near and compensates later (spacing).
- At bias 0 `apply_tag_pacing` returns the input list unchanged — byte parity. The experimental two-level cover path (`cover_two_level_enabled`, off by default) returns before this layer and deliberately ignores tag pacing for now.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_tags.py`:

```python
import math

from harmonica.algorithm import (
    AlgorithmTrack,
    apply_tag_pacing,
    generate_playlist,
    tag_pacing_factor,
)
from harmonica.config import Settings


def _algo_track(track_id: int, tags: frozenset[str] = frozenset()) -> AlgorithmTrack:
    return AlgorithmTrack(
        id=track_id,
        song_id=f"algo_{track_id}",
        title=f"Algo {track_id}",
        artist=None,
        album=None,
        media_asset_id=None,
        file_path=None,
        tags=tags,
    )


def test_tag_pacing_factor_is_zero_mean_and_directional() -> None:
    horizon = 12
    for bias in (-1.0, -0.4, 0.6, 1.0):
        total = sum(
            tag_pacing_factor(d, horizon, bias) - 1.0 for d in range(1, horizon)
        )
        assert math.isclose(total, 0.0, abs_tol=1e-9)
    # Negative bias: suppressed just after a play, compensated later in the horizon.
    assert tag_pacing_factor(1, horizon, -1.0) < 1.0
    assert tag_pacing_factor(horizon - 1, horizon, -1.0) > 1.0
    # Positive bias mirrors it; inert cases are exactly 1.0.
    assert tag_pacing_factor(1, horizon, 1.0) > 1.0
    assert tag_pacing_factor(None, horizon, 1.0) == 1.0
    assert tag_pacing_factor(horizon, horizon, 1.0) == 1.0
    assert tag_pacing_factor(3, horizon, 0.0) == 1.0


def test_apply_tag_pacing_moves_only_tagged_tracks() -> None:
    tracks = [
        _algo_track(1, frozenset({"Fun"})),
        _algo_track(2, frozenset({"Fun"})),
        _algo_track(3),
    ]
    scores = [1.0, 1.0, 1.0]
    settings = Settings(tag_clustering_bias=-1.0)
    adjusted = apply_tag_pacing(tracks, scores, 1, {"Fun": 0}, settings)
    assert adjusted[0] < 1.0 and adjusted[1] < 1.0  # same-tag, just played: suppressed
    assert adjusted[2] == 1.0  # untagged: untouched
    # Bias 0 short-circuits to the same list object (byte parity).
    neutral = Settings(tag_clustering_bias=0.0)
    assert apply_tag_pacing(tracks, scores, 1, {"Fun": 0}, neutral) is scores


def test_bias_zero_is_byte_identical_with_tags_present() -> None:
    tagged = [_algo_track(i, frozenset({"Fun"}) if i % 2 else frozenset()) for i in range(8)]
    bare = [_algo_track(i) for i in range(8)]
    settings = Settings(tag_clustering_bias=0.0)
    run_tagged = generate_playlist(tagged, {}, 30, settings, seed="parity")
    run_bare = generate_playlist(bare, {}, 30, settings, seed="parity")
    assert [item.track.id for item in run_tagged] == [item.track.id for item in run_bare]


def test_negative_bias_spaces_same_tag_songs_apart() -> None:
    # Half the pool shares one algorithm-active tag; count adjacent same-tag pairs, summed over
    # a few fixed seeds so the deterministic comparison is not hostage to one lucky draw.
    def adjacency(bias: float) -> int:
        total = 0
        for seed in ("spacing-a", "spacing-b", "spacing-c"):
            tracks = [
                _algo_track(i, frozenset({"Fun"}) if i < 10 else frozenset())
                for i in range(20)
            ]
            settings = Settings(tag_clustering_bias=bias)
            items = generate_playlist(tracks, {}, 120, settings, seed=seed)
            flags = [item.track.id < 10 for item in items]
            total += sum(1 for a, b in zip(flags, flags[1:], strict=False) if a and b)
        return total

    assert adjacency(-1.0) < adjacency(0.0) < adjacency(1.0)
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: FAIL with `ImportError` (`apply_tag_pacing`, `tag_pacing_factor` not defined) and `TypeError` for the unknown `tags` field.

- [x] **Step 3: Add the setting**

1. `src/harmonica/config.py`, after `group_clustering_bias: float = 0.0` (line 87):

```python
    # Pacing bias for algorithm-active user tags. Zero-mean over its horizon by construction, so
    # on aggregate a tag never changes how often its songs appear — only when. 0 = off.
    tag_clustering_bias: float = 0.0
```

2. `src/harmonica/settings_store.py`, after the `group_clustering_bias` `SettingDefinition` (ends line 209):

```python
    SettingDefinition(
        key="tag_clustering_bias",
        label="Tag pacing bias",
        description=(
            "For tags marked as algorithm-active in Manage tags. Negative values space "
            "same-tag songs apart; positive values let them run together. On aggregate a tag "
            "never changes how often its songs appear, only when."
        ),
        value_type="number",
        control="slider",
        default=0.0,
        minimum=-1.0,
        maximum=1.0,
        step=0.05,
    ),
```

3. `src/harmonica/schemas.py`, `SettingsRead`, after `group_clustering_bias: float` (line 192): add `tag_clustering_bias: float`.
4. `src/harmonica/playlist.py`, `settings_snapshot` (line 333): after the `"group_clustering_bias"` entry add `"tag_clustering_bias": settings.tag_clustering_bias,`.
5. `site/demo/py/driver.py`, Settings stub, after `group_clustering_bias: float = 0.0` (line 72): add `tag_clustering_bias: float = 0.0`. (The demo copies `algorithm.py` verbatim at deploy time; the stub must know the new field so the next sync keeps working. The demo library has no tags, so behaviour is unchanged.)

- [x] **Step 4: Add the algorithm layer**

In `src/harmonica/algorithm.py`:

1. `AlgorithmTrack` (line 52), after `favourite: bool = False`:

```python
    # Algorithm-active user tags (cosmetic tags never reach the algorithm). Feeds the light
    # zero-mean pacing layer in apply_tag_pacing; empty = inert.
    tags: frozenset[str] = frozenset()
```

2. After `apply_clustering_bias` (line 177), add:

```python
def tag_pacing_factor(distance: int | None, horizon: int, bias: float) -> float:
    """The light per-tag pacing factor: 1 + bias * (0.5 - distance/horizon) while the tag is
    inside its horizon, 1.0 otherwise. Mean proximity over distances 1..horizon-1 is exactly
    0.5, so the factor is zero-mean across the horizon — it shifts WHEN same-tag songs play,
    never how often on aggregate. Bounded in (0.5, 1.5) even at full bias."""
    if bias == 0.0 or distance is None or horizon <= 1 or distance >= horizon:
        return 1.0
    if distance <= 0:
        distance = 1
    return 1.0 + bias * (0.5 - distance / horizon)


def apply_tag_pacing(
    tracks: list[AlgorithmTrack],
    scores: list[float],
    current_index: int,
    tag_last_played: dict[str, int],
    settings: Settings,
) -> list[float]:
    """Selection-weight adjustment for algorithm-active tags. Applied to the selection weights
    only (like the compressed-audio bias), never the stored scores. Returns ``scores`` itself
    when the bias is 0 or nothing applies, keeping the default path byte-identical."""
    bias = min(max(settings.tag_clustering_bias, -1.0), 1.0)
    if bias == 0 or not tag_last_played:
        return scores
    horizon = min(30, max(len(tracks), 1))
    out: list[float] | None = None
    for index, track in enumerate(tracks):
        factor = 1.0
        for tag in track.tags:
            last = tag_last_played.get(tag)
            distance = None if last is None else current_index - last
            factor *= tag_pacing_factor(distance, horizon, bias)
        if factor != 1.0:
            if out is None:
                out = list(scores)
            out[index] = scores[index] * factor
    return out if out is not None else scores
```

3. In `generate_playlist`, after the `sub_group_repeat_credits = dict(...)` initialisation (line 377), add:

```python
    tag_last_played: dict[str, int] = {}
```

4. In the loop, directly after the `avoid_consecutive_compressed` block ends (line 467) and before `weighted_choice_from_indices`, add:

```python
        selection_scores = apply_tag_pacing(
            tracks, selection_scores, position, tag_last_played, settings
        )
```

5. At the end of the loop, next to the `sub_group_last_played` update (line 495-497), add:

```python
        for tag in chosen.tags:
            tag_last_played[tag] = position
```

- [x] **Step 5: Thread tags into the loaded tracks**

In `src/harmonica/playlist.py`, in the `AlgorithmTrack(...)` construction inside `load_algorithm_inputs` (line 154), after `favourite=(...)`, add:

```python
                tags=active_tag_names.get(track.id, frozenset()),
```

(`active_tag_names` already exists from Task 4's `algorithm_tag_inputs` call.)

- [x] **Step 6: Run the tests, full suite, ruff**

Run: `~/.local/bin/uv run pytest -q && ~/.local/bin/uv run ruff check src/harmonica tests`
Expected: all pass. `test_settings_coupling` and `test_api` confirm the new setting rides through `GET/PATCH /settings` as a real control.

- [x] **Step 7: Commit**

```bash
git add src/harmonica/config.py src/harmonica/settings_store.py src/harmonica/schemas.py src/harmonica/algorithm.py src/harmonica/playlist.py site/demo/py/driver.py tests/test_tags.py
git commit -m "Add zero-mean tag pacing layer with tag pacing bias setting"
```

---

### Task 6: Export and import

**Files:**
- Modify: `src/harmonica/serialization.py` (export at line 188, import at line 483, new helpers)
- Test: `tests/test_tags.py`

**Interfaces:**
- Consumes: `Tag`, `TrackTag`, `visible_tag_rows`, `set_favourite_tag`, `FAVOURITE_TAG_NAME` from Task 1.
- Produces: export payload key `"tags"`: `{"definitions": [{name, kind, shared, affects_algorithm}], "assignments": [{song_id, tag}]}` (metadata scope); `import_tags(session, raw, owner_config_id) -> int`; import summary key `"tags_applied"`. Legacy exports (favourite booleans, no tags block) keep importing through the existing favourite field, which now also syncs the Favourite tag row.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_tags.py`:

```python
def test_export_import_roundtrip_carries_tags() -> None:
    with TestClient(create_app()) as client:
        track_id = _seed_track("tags_exp_1", "Exported")
        client.post("/tags", json={"name": "Sing Along", "affects_algorithm": True})
        client.patch(f"/tracks/{track_id}", json={"tags": ["Sing Along", IGNORED_TAG_NAME]})
        payload = client.get("/library/export-json?scope=metadata").json()
        tag_block = payload["tags"]
        assert {"song_id": "tags_exp_1", "tag": "Sing Along"} in tag_block["assignments"]
        sing = next(d for d in tag_block["definitions"] if d["name"] == "Sing Along")
        assert sing["affects_algorithm"] is True

        # Re-importing the same payload is idempotent.
        first = client.post("/library/import-json", json={"payload": payload}).json()
        assert first["tags_applied"] == 0
        with SessionLocal() as session:
            rows = session.scalars(
                select(TrackTag).where(TrackTag.track_id == track_id)
            ).all()
        assert len(rows) == 2


def test_legacy_favourite_import_syncs_the_tag() -> None:
    with TestClient(create_app()) as client:
        payload = {
            "tracks": [{"song_id": "tags_legacy_1", "title": "Legacy", "favourite": True}]
        }
        client.post("/library/import-json", json={"payload": payload})
        with SessionLocal() as session:
            track = session.scalar(select(Track).where(Track.song_id == "tags_legacy_1"))
            tags = visible_tags_by_track(session, None).get(track.id, [])
        assert FAVOURITE_TAG_NAME in tags
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `~/.local/bin/uv run pytest tests/test_tags.py -q`
Expected: FAIL with `KeyError: 'tags'` and a missing Favourite tag row.

- [x] **Step 3: Implement export**

In `src/harmonica/serialization.py`:
1. Extend the models import (line 15) with `Tag`, `TrackTag`, `visible_tag_rows`, `set_favourite_tag`, `FAVOURITE_TAG_NAME`.
2. In `export_library_payload`, inside the `if with_metadata:` block after `payload["tracks"] = [...]` (line 187), add:

```python
        payload["tags"] = tags_export(session, owner_config_id)
```

3. After `cover_comparisons_payload` (line 292), add:

```python
def tags_export(session: Session, owner_config_id: int | None) -> dict[str, Any]:
    """Tag definitions plus the assignments visible to the exporting scope (a profile's own
    rows plus every shared-tag row), keyed by song_id so they survive moving devices."""
    song_by_id = dict(session.execute(select(Track.id, Track.song_id)).all())
    definitions = [
        {
            "name": tag.name,
            "kind": tag.kind,
            "shared": tag.shared,
            "affects_algorithm": tag.affects_algorithm,
        }
        for tag in session.scalars(select(Tag).order_by(Tag.name))
    ]
    assignments = [
        {"song_id": song_by_id[track_id], "tag": tag.name}
        for track_id, tag in visible_tag_rows(session, owner_config_id)
        if track_id in song_by_id
    ]
    assignments.sort(key=lambda entry: (entry["tag"], entry["song_id"]))
    return {"definitions": definitions, "assignments": assignments}
```

- [x] **Step 4: Implement import**

1. In `import_library_payload`, the summary dict (line 361) gains `"tags_applied": 0,`.
2. In the track loop, after the existing `_link_owner(...)` call (line 462), add:

```python
        if fav_value is not None:
            # Keep the Favourite tag in step with a legacy favourite boolean.
            set_favourite_tag(session, track.id, fav_value, owner_config_id)
```

3. After the `session.flush()` that closes the track loop (line 463), add:

```python
    summary["tags_applied"] = import_tags(
        session, payload.get("tags"), owner_config_id=owner_config_id
    )
```

4. After `import_cover_comparisons` (line 631), add:

```python
def import_tags(session: Session, raw: Any, owner_config_id: int | None = None) -> int:
    """Merge a tags block: definitions by name (system tags never demoted or reflagged),
    assignments idempotently under the shared/per-profile owner rule."""
    if not isinstance(raw, dict):
        return 0
    tags_by_name = {tag.name: tag for tag in session.scalars(select(Tag))}
    for entry in _dict_list(raw.get("definitions")):
        name = _text(entry.get("name"), max_len=120)
        if name is None:
            continue
        tag = tags_by_name.get(name)
        if tag is None:
            tag = Tag(name=name, kind="custom")
            session.add(tag)
            session.flush()
            tags_by_name[name] = tag
        if tag.kind != "system":
            if isinstance(entry.get("shared"), bool):
                tag.shared = entry["shared"]
            if isinstance(entry.get("affects_algorithm"), bool):
                tag.affects_algorithm = entry["affects_algorithm"]
    track_by_song = {track.song_id: track for track in session.scalars(select(Track))}
    existing = {
        (row.track_id, row.tag_id, row.owner_config_id)
        for row in session.scalars(select(TrackTag))
    }
    applied = 0
    for entry in _dict_list(raw.get("assignments")):
        name = _text(entry.get("tag"), max_len=120)
        track = track_by_song.get(entry.get("song_id"))
        tag = tags_by_name.get(name) if name else None
        if track is None or tag is None:
            continue
        row_owner = None if tag.shared else owner_config_id
        key = (track.id, tag.id, row_owner)
        if key in existing:
            continue
        existing.add(key)
        session.add(TrackTag(track_id=track.id, tag_id=tag.id, owner_config_id=row_owner))
        applied += 1
    session.flush()
    return applied
```

- [x] **Step 5: Run the tests, full suite, ruff**

Run: `~/.local/bin/uv run pytest -q && ~/.local/bin/uv run ruff check src/harmonica tests`
Expected: all pass (`test_export_import.py` confirms old payloads still import unchanged).

- [x] **Step 6: Commit**

```bash
git add src/harmonica/serialization.py tests/test_tags.py
git commit -m "Carry tags through library export and import"
```

---

### Task 7: Front end — editor section, library facets, queue picker, settings

**Files:**
- Modify: `web/src/types.ts` (new `Tag` type; `Track.tags`; `AppSettings.tag_clustering_bias`; `SettingControl` key union; `ImportSummary.tags_applied`)
- Modify: `web/src/api.ts` (tag endpoints; `updateTrack` sends `tags`; `generateQueue` sends `tags`)
- Modify: `web/src/App.tsx` (state + refresh; `generateQueue`; `QueueView` picker; `LibraryView` facets/search/muting + `TagManager`; `TrackEditor` Tags section + star sync; `SETTING_SECTIONS`; `buildFacets`)
- Modify: `web/src/styles.css` (chip toggle, ignored muting, tag manager, new-tag row)

**Interfaces:**
- Consumes: `GET/POST/PATCH/DELETE /tags`, `TrackRead.tags`, `QueueGenerateRequest.tags`, the `tag_clustering_bias` control.
- Produces: `Tag` type `{ id, name, kind, shared, affects_algorithm, track_count }`; `api.listTags/createTag/updateTag/deleteTag`; `api.generateQueue(length, seed?, configId?, tags?)`.

- [x] **Step 1: Types**

In `web/src/types.ts`:
1. After the `Embed` type (line 28), add:

```ts
// A user tag. System tags (Favourite, Ignored) are fixed; custom tags are user-managed.
// `shared` = assignments are household-wide instead of per-profile; `affects_algorithm`
// = the tag feeds the light pacing layer (cosmetic otherwise).
export type Tag = {
  id: number;
  name: string;
  kind: "system" | "custom" | string;
  shared: boolean;
  affects_algorithm: boolean;
  track_count: number;
};
```

2. `Track` (line 30): after `cooldown_tags: string[];` add `tags?: string[];`.
3. `SettingControl` key union (line 96): after `| "group_clustering_bias"` add `| "tag_clustering_bias"`.
4. `AppSettings` (line 152): after `group_clustering_bias: number;` add `tag_clustering_bias: number;`.
5. `ImportSummary` (line 316): add `tags_applied?: number;`.

- [x] **Step 2: API client**

In `web/src/api.ts`:
1. Add `Tag` to the type import from `./types`.
2. In `updateTrack`'s body (after `cooldown_tags: track.cooldown_tags,` line 111), add `tags: track.tags ?? [],`.
3. Change `generateQueue` to:

```ts
  generateQueue: (length: number, seed?: string, configId?: number | null, tags?: string[]) =>
    request<QueueRun>("/queue/generate", {
      method: "POST",
      body: JSON.stringify({
        length,
        seed: seed || null,
        explain: true,
        ui_active: true,
        config_id: configId ?? null,
        tags: tags && tags.length ? tags : null
      })
    }),
```

4. After `claimConfig` (line 224), add:

```ts
  ,
  // --- Tags (system tags Favourite/Ignored are fixed; custom tags are user-managed) ---
  listTags: () => request<Tag[]>("/tags"),
  createTag: (body: { name: string; shared?: boolean; affects_algorithm?: boolean }) =>
    request<Tag>("/tags", { method: "POST", body: JSON.stringify(body) }),
  updateTag: (id: number, body: { name?: string; shared?: boolean; affects_algorithm?: boolean }) =>
    request<Tag>(`/tags/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTag: (id: number) =>
    fetch(`/tags/${id}`, { method: "DELETE", headers: authHeaders() }).then((response) => {
      if (!response.ok && response.status !== 404) {
        throw new Error(`Delete failed: ${response.status}`);
      }
    })
```

- [x] **Step 3: App state and generation**

In `web/src/App.tsx`:
1. Add `Tag` to the types import and `const [tags, setTags] = useState<Tag[]>([]);` beside the other state.
2. In `refreshAll` (line 242), after the youtubeConfig line, add:

```ts
      void api.listTags().then(setTags).catch(() => setTags([]));
```

3. Add a refresh helper near `refreshStats`:

```ts
  function refreshTags() {
    void api.listTags().then(setTags).catch(() => undefined);
  }
```

4. Change `generateQueue` (line 282) to accept and forward tags:

```ts
  async function generateQueue(length: number, seed: string, queueTags: string[]) {
    setBusy(true);
    setError(null);
    try {
      const run = await api.generateQueue(
        length,
        seed.trim() || undefined,
        activeConfig?.id ?? null,
        queueTags
      );
      player.loadQueue(run, { autoplay: true });
      void refreshSavedRuns();
    } catch (err) {
      setError(message(err, "Could not generate a queue"));
    } finally {
      setBusy(false);
    }
  }
```

5. Pass `tags={tags}` to `QueueView` (call site near line 475) and `tags={tags}` plus `onTagsChanged={refreshTags}` to `LibraryView`. After a track save (`onSave` path), also call `refreshTags()` so new tag names appear in the chip lists.

- [x] **Step 4: Queue tag picker**

In `QueueView` (line 777):
1. Add props `tags: Tag[];` and change `onGenerate: (length: number, seed: string, tags: string[]) => void;`.
2. Add state `const [queueTags, setQueueTags] = useState<string[]>([]);` and above the generate row inside the generate-card (line 866), add:

```tsx
          <div className="queue-tag-picker">
            {props.tags
              .filter((tag) => tag.name !== "Ignored" && tag.track_count > 0)
              .map((tag) => {
                const on = queueTags.includes(tag.name);
                return (
                  <button
                    key={tag.id}
                    className={`chip toggle ${on ? "on" : ""}`}
                    onClick={() =>
                      setQueueTags((cur) =>
                        on ? cur.filter((name) => name !== tag.name) : [...cur, tag.name]
                      )
                    }
                  >
                    {tag.name} <b>{tag.track_count}</b>
                  </button>
                );
              })}
          </div>
          {queueTags.length ? (
            <small className="queue-tag-note">
              Only songs tagged {queueTags.join(" or ")} will be queued.
            </small>
          ) : null}
```

3. The Generate button becomes `onClick={() => props.onGenerate(length, seed, queueTags)}`.

- [x] **Step 5: Library facets, search, muting, manager**

In `App.tsx`:
1. `buildFacets` (line 3057): add a `tag: new Map()` counter, count `for (const name of track.tags ?? [])`, and return `tag: toFacets("tag", counters.tag)` (extend the return type accordingly).
2. `LibraryView` props gain `tags: Tag[];` and `onTagsChanged: () => void;`. Add state `const [manageTags, setManageTags] = useState(false);`.
3. In the facet rail (after the Variant families group, line 1395), add:

```tsx
        <FacetGroup title="Tags" facets={facets.tag} active={facet} onPick={setFacet} />
        <button className="facet manage-tags" onClick={() => setManageTags((open) => !open)}>
          {manageTags ? "Close tag manager" : "Manage tags…"}
        </button>
        {manageTags ? <TagManager tags={props.tags} onChanged={props.onTagsChanged} /> : null}
```

4. In the `filtered` memo (line 1354), handle the tag facet before the group check:

```ts
        if (type === "tag") {
          if (!(track.tags ?? []).includes(name)) {
            return false;
          }
        } else if (type === "variant") {
```

(keep the existing variant/group branches after it), and extend the search haystack (line 1367) with `...(track.tags ?? [])`.
5. Mute ignored cards: the track-card `className` (line 1433) becomes:

```tsx
                className={`track-card ${selected?.id === track.id ? "active" : ""} ${(track.tags ?? []).includes("Ignored") ? "ignored" : ""}`}
```

6. Pass `tags={props.tags}` into `<TrackEditor …>`.
7. Add the `TagManager` component after `FacetGroup`:

```tsx
// Rename, delete, and flag custom tags. System tags (Favourite, Ignored) are fixed.
function TagManager(props: { tags: Tag[]; onChanged: () => void }) {
  const [name, setName] = useState("");
  async function run(action: Promise<unknown>) {
    try {
      await action;
    } finally {
      props.onChanged();
    }
  }
  return (
    <div className="tag-manager">
      {props.tags.map((tag) => (
        <div key={tag.id} className="tag-row">
          <span className="tag-name">
            {tag.name} <b>{tag.track_count}</b>
          </span>
          {tag.kind === "system" ? (
            <small>built-in</small>
          ) : (
            <span className="tag-ops">
              <label title="Assignments are shared by every profile in the household">
                <input
                  type="checkbox"
                  checked={tag.shared}
                  onChange={(e) => void run(api.updateTag(tag.id, { shared: e.target.checked }))}
                />
                shared
              </label>
              <label title="Feeds the tag pacing bias in Settings">
                <input
                  type="checkbox"
                  checked={tag.affects_algorithm}
                  onChange={(e) =>
                    void run(api.updateTag(tag.id, { affects_algorithm: e.target.checked }))
                  }
                />
                algorithm
              </label>
              <button
                className="mini"
                title="Rename tag"
                onClick={() => {
                  const next = window.prompt(`Rename tag "${tag.name}" to:`, tag.name)?.trim();
                  if (next && next !== tag.name) {
                    void run(api.updateTag(tag.id, { name: next }));
                  }
                }}
              >
                <Pencil size={12} />
              </button>
              <button
                className="mini"
                title="Delete tag"
                onClick={() => {
                  if (window.confirm(`Delete the tag "${tag.name}"? Its assignments go too.`)) {
                    void run(api.deleteTag(tag.id));
                  }
                }}
              >
                <X size={12} />
              </button>
            </span>
          )}
        </div>
      ))}
      <div className="new-tag-row">
        <input
          value={name}
          placeholder="New tag name…"
          onChange={(e) => setName(e.target.value)}
        />
        <button
          className="mini-text"
          onClick={() => {
            const clean = name.trim();
            if (clean) {
              setName("");
              void run(api.createTag({ name: clean }));
            }
          }}
        >
          Add
        </button>
      </div>
    </div>
  );
}
```

- [x] **Step 6: Track editor Tags section and star sync**

In `TrackEditor` (line 1631):
1. Add prop `tags: Tag[];` and state `const [newTag, setNewTag] = useState("");` plus:

```tsx
  function toggleTag(name: string) {
    setDraft((current) => {
      const cur = current.tags ?? [];
      const next = cur.includes(name) ? cur.filter((t) => t !== name) : [...cur, name];
      // Favourite rides in both places; keep the star in step with the chip.
      const favourite = name === "Favourite" ? next.includes("Favourite") : current.favourite;
      return { ...current, tags: next, favourite };
    });
  }
```

2. The star button `onClick` (line 1684) becomes `onClick={() => toggleTag("Favourite")}` (the `favourite` display value keeps reading `draft.favourite`).
3. After the Details editor-section (line 1769), add:

```tsx
      <div className="editor-section">
        <h5>Tags</h5>
        <div className="tag-chips">
          {[
            ...props.tags.filter((tag) => tag.kind === "custom").map((tag) => tag.name),
            ...(draft.tags ?? []).filter(
              (name) =>
                name !== "Favourite" &&
                name !== "Ignored" &&
                !props.tags.some((tag) => tag.name === name)
            )
          ].map((name) => {
            const on = (draft.tags ?? []).includes(name);
            return (
              <button
                key={name}
                className={`chip toggle ${on ? "on" : ""}`}
                onClick={() => toggleTag(name)}
              >
                {name}
              </button>
            );
          })}
        </div>
        <div className="new-tag-row">
          <input
            value={newTag}
            placeholder="New tag…"
            onChange={(e) => setNewTag(e.target.value)}
          />
          <button
            className="mini-text"
            onClick={() => {
              const clean = newTag.trim();
              if (clean) {
                setNewTag("");
                toggleTag(clean);
              }
            }}
          >
            Add
          </button>
        </div>
        <label className="check-line">
          <input
            type="checkbox"
            checked={(draft.tags ?? []).includes("Ignored")}
            onChange={() => toggleTag("Ignored")}
          />
          Ignored: never included in generated queues (manual play still works)
        </label>
      </div>
```

- [x] **Step 7: Settings section and styles**

1. In `SETTING_SECTIONS`, the "Anti-repetition & variety" entry (line 2099): keys become `["group_cooldown_floor", "sub_group_cooldown_floor", "group_clustering_bias", "tag_clustering_bias"]`.
2. In `web/src/styles.css`, append:

```css
/* Tags */
.chip.toggle {
  cursor: pointer;
  background: transparent;
  border: 1px solid rgba(32, 106, 93, 0.35);
  color: #206a5d;
}
.chip.toggle.on {
  background: #206a5d;
  border-color: #206a5d;
  color: #fff;
}
.tag-chips,
.queue-tag-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.track-card.ignored {
  opacity: 0.55;
}
.tag-manager {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(32, 106, 93, 0.08);
  font-size: 0.85em;
}
.tag-manager .tag-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.tag-manager .tag-ops {
  display: flex;
  align-items: center;
  gap: 6px;
}
.new-tag-row {
  display: flex;
  gap: 6px;
}
.new-tag-row input {
  flex: 1;
  min-width: 0;
}
.queue-tag-note {
  display: block;
  margin-bottom: 6px;
  color: #206a5d;
}
```

(If `styles.css` uses theme variables for the accent, use those instead of the raw hex — match the file's existing idiom.)

- [x] **Step 8: Build**

Run: `cd web && npm run build`
Expected: build succeeds with no TypeScript errors. Fix any prop-threading errors the compiler reports (the call sites for `QueueView`, `LibraryView`, and `TrackEditor` all changed).

- [x] **Step 9: Commit**

```bash
git add web/src/types.ts web/src/api.ts web/src/App.tsx web/src/styles.css
git commit -m "Add tags UI: editor section, library facets, queue picker, manager"
```

---

### Task 8: Final verification

**Files:**
- Modify: `docs/superpowers/specs/2026-07-12-custom-tags-design.md` (status line only, if all green)

- [x] **Step 1: Full checks**

Run:
```bash
~/.local/bin/uv run pytest -q
~/.local/bin/uv run ruff check src/harmonica tests
cd web && npm run build
```
Expected: everything green.

- [x] **Step 2: Manual smoke (only if a daemon is NOT already on port 8765)**

Optionally start `~/.local/bin/uv run harmonica serve` against a scratch `HARMONICA_HOME`, and exercise: create a tag, tag a track, filter by it, ignore a track, generate a queue restricted to a tag. Never kill an existing daemon on 8765.

- [x] **Step 3: Update the spec status and commit**

Change the spec's status line to `Status: implemented 2026-07-12.` Then:

```bash
git add docs/superpowers/specs/2026-07-12-custom-tags-design.md
git commit -m "Mark custom tags spec implemented"
```

- [x] **Step 4: Report**

Summarise for the owner: what shipped, test counts, and the follow-up note that a website paragraph about organising with tags is pending their word (task #67). Do NOT push anything.
