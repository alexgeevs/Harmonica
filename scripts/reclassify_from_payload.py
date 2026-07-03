#!/usr/bin/env python3
"""Corrective reclassify: CLEAR a payload's tracks (groups / cooldown-tags / sub_group), then apply
the payload via the canonical import path.

Why this exists: POST /library/import-json only ADDS memberships (serialization.py) — it never
removes them, so a plain re-import cannot pull a song OUT of a wrong group (e.g. a bad group).
This helper clears first, so a corrected classification actually replaces the old one. Local /
no-profile (owner_config_id=None) mode only. It backs up the SQLite file before writing.

Usage:
  python scripts/reclassify_from_payload.py payload.json            # dry run (no writes)
  python scripts/reclassify_from_payload.py payload.json --apply     # writes (backup taken first)

Stop the daemon before --apply (SQLite is single-writer).
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, select

from harmonica.config import get_settings
from harmonica.db import SessionLocal, init_db
from harmonica.models import GroupMembership, Track, TrackCooldownTag, WeightGroup
from harmonica.serialization import import_library_payload


def _db_path() -> Path | None:
    url = get_settings().db_url
    if url.startswith("sqlite"):
        return Path(url.split(":///")[-1])
    return None


def main() -> int:
    args = sys.argv[1:]
    apply = "--apply" in args
    positional = [a for a in args if not a.startswith("-")]
    if not positional:
        print("usage: reclassify_from_payload.py payload.json [--apply]")
        return 2

    payload = json.loads(Path(positional[0]).read_text())
    song_ids = [t["song_id"] for t in payload.get("tracks", []) if t.get("song_id")]

    init_db()
    with SessionLocal() as s:
        found = {t.song_id for t in s.scalars(select(Track).where(Track.song_id.in_(song_ids)))}
    missing = [sid for sid in song_ids if sid not in found]
    print(f"payload tracks: {len(song_ids)}   matched: {len(found)}   missing: {len(missing)}")
    if missing:
        tail = "..." if len(missing) > 20 else ""
        print("  missing song_ids:", ", ".join(missing[:20]), tail)

    if not apply:
        print("\nDRY RUN - would clear groups/cooldown-tags/sub_group for the matched tracks, then")
        print("apply the payload and prune any now-empty groups. Re-run with --apply to write")
        print("(a timestamped backup of the SQLite file is taken first).")
        return 0

    dbp = _db_path()
    if not (dbp and dbp.exists()):
        print("WARNING: could not locate the sqlite file to back up; aborting for safety.")
        return 1
    bak = dbp.with_suffix(dbp.suffix + f".bak.{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(dbp, bak)
    print(f"backup: {bak}")

    # 1) Clear old memberships / tags / sub_group for the payload's tracks.
    with SessionLocal() as s:
        ids = [t.id for t in s.scalars(select(Track).where(Track.song_id.in_(song_ids)))]
        s.execute(delete(GroupMembership).where(GroupMembership.track_id.in_(ids)))
        s.execute(delete(TrackCooldownTag).where(TrackCooldownTag.track_id.in_(ids)))
        for tr in s.scalars(select(Track).where(Track.id.in_(ids))):
            tr.sub_group = None
        s.commit()
    print(f"cleared groups/cooldown-tags/sub_group for {len(ids)} tracks")

    # 2) Apply the payload through the canonical importer (adds the corrected classification).
    with SessionLocal() as s:
        import_library_payload(s, payload, settings=get_settings(), owner_config_id=None)
    print("applied payload via import_library_payload")

    # 3) Prune groups that ended up with no members (e.g. dissolved junk groups).
    with SessionLocal() as s:
        rows = s.execute(
            select(WeightGroup.id, WeightGroup.name)
            .outerjoin(GroupMembership, GroupMembership.group_id == WeightGroup.id)
            .group_by(WeightGroup.id)
            .having(func.count(GroupMembership.id) == 0)
        ).all()
        for gid, _ in rows:
            s.execute(delete(WeightGroup).where(WeightGroup.id == gid))
        s.commit()
        if rows:
            names = ", ".join(n for _, n in rows[:20]) + ("..." if len(rows) > 20 else "")
            print(f"pruned {len(rows)} now-empty groups: {names}")
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
