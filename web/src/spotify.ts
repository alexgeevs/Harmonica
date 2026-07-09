import type { Track } from "./types";

// Reported by GET /spotify/config. `has_credentials` is only whether app credentials are present
// on the server (never the credentials themselves).
export type SpotifyConfig = {
  enabled: boolean;
  has_credentials: boolean;
};

// One track's metadata from a Spotify playlist. Mirrors the backend SpotifyTrackRead schema.
export type SpotifyTrack = {
  name: string;
  artists: string[];
  album?: string | null;
  duration_ms?: number | null;
  spotify_id?: string | null;
  url?: string | null;
};

export type SpotifyPlaylist = {
  id: string;
  name?: string | null;
  tracks: SpotifyTrack[];
  truncated: boolean;
};

function normalise(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/** Lowercased, punctuation-insensitive titles of the local library, for a loose "already have it"
 * hint. This is only a display cue, never authoritative — a shared title can collide. */
export function libraryTitleSet(tracks: Track[]): Set<string> {
  return new Set(tracks.map((track) => normalise(track.title)).filter(Boolean));
}

export function isLikelyInLibrary(track: SpotifyTrack, titles: Set<string>): boolean {
  return titles.has(normalise(track.name));
}
