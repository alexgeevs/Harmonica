import type { LibraryExport, LibraryGroupRef, LibraryTrackPayload } from "./types";

export type FieldChange = { field: string; before: unknown; after: unknown };

export type TrackDiff = {
  song_id: string;
  title: string;
  status: "new" | "modified";
  fieldChanges: FieldChange[];
  groupsAdded: string[];
  groupsRemoved: string[];
  ratingChanges: { key: string; before: number | null; after: number | null }[];
  proposed: LibraryTrackPayload;
};

export type LibraryDiff = {
  tracks: TrackDiff[];
  unchanged: number;
  missingFromProposed: number;
};

const SCALAR_FIELDS: (keyof LibraryTrackPayload)[] = [
  "title",
  "artist",
  "album",
  "has_lyrics",
  "sub_group",
  "manual_multiplier"
];

function normalize(value: unknown): unknown {
  if (value === undefined || value === "") {
    return null;
  }
  return value;
}

function groupNames(groups: LibraryGroupRef[] | undefined): string[] {
  return (groups ?? []).map((group) => group.name).sort();
}

/** Compare a proposed library against the current one, keyed by song_id. */
export function diffLibrary(current: LibraryExport, proposed: LibraryExport): LibraryDiff {
  const currentById = new Map(current.tracks.map((track) => [track.song_id, track]));
  const proposedIds = new Set(proposed.tracks.map((track) => track.song_id));
  const diffs: TrackDiff[] = [];
  let unchanged = 0;

  for (const next of proposed.tracks) {
    const prev = currentById.get(next.song_id);
    if (!prev) {
      diffs.push({
        song_id: next.song_id,
        title: next.title,
        status: "new",
        fieldChanges: [],
        groupsAdded: groupNames(next.groups),
        groupsRemoved: [],
        ratingChanges: Object.entries(next.ratings ?? {}).map(([key, value]) => ({
          key,
          before: null,
          after: value
        })),
        proposed: next
      });
      continue;
    }

    const fieldChanges: FieldChange[] = [];
    for (const field of SCALAR_FIELDS) {
      const before = normalize(prev[field]);
      const after = normalize(next[field]);
      if (before !== after) {
        fieldChanges.push({ field, before, after });
      }
    }

    const prevGroups = new Set(groupNames(prev.groups));
    const nextGroups = new Set(groupNames(next.groups));
    const groupsAdded = [...nextGroups].filter((name) => !prevGroups.has(name));
    const groupsRemoved = [...prevGroups].filter((name) => !nextGroups.has(name));

    const ratingChanges: TrackDiff["ratingChanges"] = [];
    const keys = new Set([...Object.keys(prev.ratings ?? {}), ...Object.keys(next.ratings ?? {})]);
    for (const key of keys) {
      const before = prev.ratings?.[key] ?? null;
      const after = next.ratings?.[key] ?? null;
      if (before !== after) {
        ratingChanges.push({ key, before, after });
      }
    }

    if (fieldChanges.length || groupsAdded.length || groupsRemoved.length || ratingChanges.length) {
      diffs.push({
        song_id: next.song_id,
        title: next.title || prev.title,
        status: "modified",
        fieldChanges,
        groupsAdded,
        groupsRemoved,
        ratingChanges,
        proposed: next
      });
    } else {
      unchanged += 1;
    }
  }

  const missingFromProposed = current.tracks.filter((track) => !proposedIds.has(track.song_id)).length;
  return { tracks: diffs, unchanged, missingFromProposed };
}

/** Parse and lightly validate a pasted/uploaded library JSON. */
export function parseProposedLibrary(text: string): LibraryExport {
  const parsed = JSON.parse(text) as LibraryExport;
  if (!parsed || !Array.isArray(parsed.tracks)) {
    throw new Error("That file doesn't look like a Harmonica library export (missing a tracks array).");
  }
  for (const track of parsed.tracks) {
    if (typeof track.song_id !== "string") {
      throw new Error("Every track needs a song_id to match against your library.");
    }
  }
  return parsed;
}
