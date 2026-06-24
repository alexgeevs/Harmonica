import type { AppSettings, PlaybackEventCreate, QueueRun, RatingFactor, Track } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {})
    },
    ...options
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  settings: () => request<AppSettings>("/settings"),
  updateSettings: (values: Record<string, number | boolean>) =>
    request<AppSettings>("/settings", {
      method: "PATCH",
      body: JSON.stringify({ values })
    }),
  ratingFactors: () => request<RatingFactor[]>("/rating-factors"),
  tracks: () => request<Track[]>("/tracks"),
  updateTrack: (track: Track) =>
    request<Track>(`/tracks/${track.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        title: track.title,
        artist: track.artist,
        album: track.album,
        has_lyrics: track.has_lyrics,
        sub_group: track.sub_group,
        manual_multiplier: track.manual_multiplier,
        groups: track.groups.map((group) => ({
          name: group.name,
          group_type: group.group_type,
          share: group.share ?? null
        })),
        cooldown_tags: track.cooldown_tags,
        ratings: track.ratings
      })
    }),
  scan: (library: string) =>
    request<{ scanned: number; created_tracks: number; created_assets: number }>(
      "/scan",
      {
        method: "POST",
        body: JSON.stringify({ library })
      }
    ),
  generateQueue: (length: number, seed?: string) =>
    request<QueueRun>("/queue/generate", {
      method: "POST",
      body: JSON.stringify({ length, seed: seed || null, explain: true })
    }),
  recordPlaybackEvent: (event: PlaybackEventCreate) =>
    request("/playback-events", {
      method: "POST",
      body: JSON.stringify(event)
    })
};
