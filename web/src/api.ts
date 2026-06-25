import type {
  AppSettings,
  LibraryExport,
  PlaybackEvent,
  PlaybackEventCreate,
  QueueRun,
  RatingFactor,
  RunSummary,
  StatsSummary,
  Track
} from "./types";

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
  stats: () => request<StatsSummary>("/stats/summary"),
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
      body: JSON.stringify({ length, seed: seed || null, explain: true, ui_active: true })
    }),
  recordPlaybackEvent: (event: PlaybackEventCreate) =>
    request("/playback-events", {
      method: "POST",
      body: JSON.stringify(event)
    }),
  playbackEvents: (limit = 200) =>
    request<PlaybackEvent[]>(`/playback-events?limit=${limit}`),
  getRun: (id: number) => request<QueueRun>(`/playlist-runs/${id}`),
  // Saved-queue endpoints are additive on the backend; callers should tolerate 404.
  listRuns: (limit = 50) => request<RunSummary[]>(`/playlist-runs?limit=${limit}`),
  renameRun: (id: number, name: string) =>
    request<RunSummary>(`/playlist-runs/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name })
    }),
  deleteRun: (id: number) =>
    fetch(`/playlist-runs/${id}`, { method: "DELETE" }).then((response) => {
      if (!response.ok && response.status !== 404) {
        throw new Error(`Delete failed: ${response.status}`);
      }
    }),
  updateTrackFields: (id: number, fields: Record<string, unknown>) =>
    request<Track>(`/tracks/${id}`, { method: "PATCH", body: JSON.stringify(fields) }),
  exportLibrary: () => request<LibraryExport>("/library/export-json"),
  importLibrary: (payload: LibraryExport) =>
    request<{ ok: boolean }>("/library/import-json", {
      method: "POST",
      body: JSON.stringify({ payload })
    })
};

/** True when the saved-queues backend endpoints are available. */
export async function savedQueuesSupported(): Promise<boolean> {
  try {
    await api.listRuns(1);
    return true;
  } catch {
    return false;
  }
}
