import type { LibraryExport, LibraryTrackPayload } from "./types";

// The video-list importer. The browser posts a pasted blob of links to the Harmonica backend, which
// reads each video's metadata server-side (keyless oEmbed, or the Data API when the user picks a
// factor that needs it). The browser never contacts YouTube for this. Results are proposed tracks
// that flow through the same review-before-import screen used for agent curation.

export type YouTubeVideoRead = {
  video_id: string;
  title?: string | null;
  channel?: string | null;
  duration_seconds?: number | null;
  available: boolean;
  likely_song: boolean;
};

// A suggested "these are the same song" grouping. Always shown for the user to confirm before any
// sub-group is applied, so a wrong guess can never merge two songs on its own.
export type YouTubeCluster = {
  key: string;
  suggested_sub_group: string;
  song_ids: string[];
  reason: string;
};

export type YouTubeImportPreview = {
  videos: YouTubeVideoRead[];
  tracks: LibraryTrackPayload[];
  clusters: YouTubeCluster[];
  used_api: boolean;
  truncated: boolean;
  requested: number;
};

// The factors the picker offers, matching the backend's known set. `needsKey` factors read extra
// detail through YouTube's Data API, which needs the user's own key; the rest are keyless (oEmbed).
export type ImportFactor = {
  key: string;
  label: string;
  hint: string;
  needsKey: boolean;
};

export const IMPORT_FACTORS: ImportFactor[] = [
  { key: "channel", label: "Uploader", hint: "Group by who uploaded it.", needsKey: false },
  { key: "title", label: "Title", hint: "Split “Artist - Title” and spot covers or live versions.", needsKey: false },
  { key: "duration", label: "Duration", hint: "Flag videos too long to be a single song.", needsKey: true },
  { key: "description", label: "Description", hint: "Match the same song across differently titled videos.", needsKey: true },
  { key: "category", label: "Category", hint: "Flag videos YouTube does not class as music.", needsKey: true },
  { key: "tags", label: "Tags", hint: "Read the uploader's tags.", needsKey: true },
  { key: "published", label: "Publish date", hint: "Read when each video went up.", needsKey: true }
];

export function factorNeedsKey(selected: Set<string>): boolean {
  return IMPORT_FACTORS.some((factor) => factor.needsKey && selected.has(factor.key));
}

/** Apply the clusters the user confirmed: every track in a confirmed cluster is given that
 *  cluster's suggested sub-group (its version family). Returns a fresh library export ready for
 *  the diff-review. Tracks in no confirmed cluster are left untouched. */
export function applyClusters(
  tracks: LibraryTrackPayload[],
  clusters: YouTubeCluster[],
  confirmedKeys: Set<string>
): LibraryExport {
  const subGroupBySong = new Map<string, string>();
  for (const cluster of clusters) {
    if (!confirmedKeys.has(cluster.key)) {
      continue;
    }
    for (const songId of cluster.song_ids) {
      subGroupBySong.set(songId, cluster.suggested_sub_group);
    }
  }
  return {
    tracks: tracks.map((track) => {
      const subGroup = subGroupBySong.get(track.song_id);
      return subGroup ? { ...track, sub_group: subGroup } : track;
    })
  };
}
