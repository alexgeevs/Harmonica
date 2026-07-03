#!/usr/bin/env python3
"""Read-only verification of a Harmonica classification. NEVER writes to the DB.

Usage:
  python scripts/verify_classification.py [db_path] [payload.json]

Defaults db to .harmonica/harmonica.db. If a payload.json is given, also cross-checks that the DB's
group memberships match what was classified. Exit code 1 if any flags are raised, else 0.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def find_db(args: list[str]) -> str:
    for a in args:
        if a.endswith(".db"):
            return a
    return ".harmonica/harmonica.db"


def find_payload(args: list[str]) -> str | None:
    for a in args:
        if a.endswith(".json"):
            return a
    return None


def col_exists(cur, table: str, col: str) -> bool:
    return col in [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]


def main() -> int:
    args = sys.argv[1:]
    dbp = find_db(args)
    payload_path = find_payload(args)
    if not Path(dbp).exists():
        print(f"DB not found: {dbp}")
        return 2

    c = sqlite3.connect(dbp)
    cur = c.cursor()
    flags: list[str] = []

    total = cur.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    ngroups = cur.execute("SELECT COUNT(*) FROM weight_groups").fetchone()[0]
    print(f"tracks: {total}   weight_groups: {ngroups}")
    has_type = col_exists(cur, "weight_groups", "group_type")

    # --- Group sizes (flag any group that swallows > 25% of the library) ---
    rows = cur.execute(
        """SELECT wg.name, wg.group_type, COUNT(gm.track_id) n
           FROM weight_groups wg LEFT JOIN group_memberships gm ON gm.group_id = wg.id
           GROUP BY wg.id ORDER BY n DESC"""
    ).fetchall()
    print("\nGroup sizes (top 15):")
    for name, gtype, n in rows[:15]:
        print(f"  {n:>3}  [{gtype}]  {name[:50]}")
    for name, _gtype, n in rows:
        if total and n > 0.25 * total:
            pct = 100 * n / total
            flags.append(f"OVER-BROAD group '{name}' = {n} songs ({pct:.0f}% of library)")

    # --- Over-tagged: aboutness (non-artist) memberships per song ---
    if has_type:
        over = cur.execute(
            """SELECT t.song_id, COUNT(*) k FROM tracks t
               JOIN group_memberships gm ON gm.track_id = t.id
               JOIN weight_groups wg ON wg.id = gm.group_id
               WHERE wg.group_type <> 'artist'
               GROUP BY t.id HAVING k > 3 ORDER BY k DESC"""
        ).fetchall()
        for sid, k in over:
            flags.append(f"OVER-TAGGED {sid}: {k} aboutness groups (>3; ~2 is the guideline)")

    # --- Artist share sums (~0.5 per song once artists are classified) ---
    if has_type:
        sums = cur.execute(
            """SELECT t.song_id, ROUND(SUM(COALESCE(gm.share, 0)), 3)
               FROM tracks t JOIN group_memberships gm ON gm.track_id = t.id
               JOIN weight_groups wg ON wg.id = gm.group_id
               WHERE wg.group_type = 'artist' GROUP BY t.id"""
        ).fetchall()
        print(f"\nsongs with artist groups: {len(sums)}")
        for sid, x in [(s, v) for s, v in sums if abs((v or 0) - 0.5) > 0.02][:20]:
            flags.append(f"ARTIST-SHARE {sid}: sum={x} (expected ~0.5)")

    # --- sub_group rendition families ---
    fam = cur.execute(
        """SELECT sub_group, COUNT(*),
                  SUM(CASE WHEN is_original_rendition THEN 1 ELSE 0 END)
           FROM tracks WHERE sub_group IS NOT NULL AND sub_group <> ''
           GROUP BY sub_group"""
    ).fetchall()
    print(f"\nsub_group families: {len(fam)} (2+ members: {sum(1 for _, n, _ in fam if n >= 2)})")
    for s, n, o in fam:
        if n == 1:
            flags.append(f"SINGLETON sub_group '{s[:40]}' — should be null (needs 2+ renditions)")
        elif o != 1:
            flags.append(f"sub_group '{s[:40]}': {n} members but {o} originals (need exactly 1)")

    # --- Optional: cross-check DB vs payload ---
    if payload_path:
        payload = json.loads(Path(payload_path).read_text())
        db_groups: dict[str, set[str]] = {}
        for sid, gname in cur.execute(
            """SELECT t.song_id, wg.name FROM tracks t
               JOIN group_memberships gm ON gm.track_id = t.id
               JOIN weight_groups wg ON wg.id = gm.group_id"""
        ):
            db_groups.setdefault(sid, set()).add(gname)
        mism = 0
        for t in payload.get("tracks", []):
            sid = t.get("song_id")
            want = {g["name"] for g in t.get("groups", [])}
            got = db_groups.get(sid, set())
            if want != got:
                mism += 1
                if mism <= 15:
                    flags.append(f"MISMATCH {sid}: payload={sorted(want)} db={sorted(got)}")
        print(f"\npayload cross-check: {len(payload.get('tracks', []))} tracks, {mism} mismatched")

    print("\n" + ("=" * 60))
    if flags:
        print(f"{len(flags)} FLAG(S):")
        for f in flags:
            print("  ! " + f)
        return 1
    print("OK - no flags; classification looks consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
