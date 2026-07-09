import type {
  AppSettings,
  CoverComparisonPair,
  CoverSetRead,
  CoverVerdict,
  DeviceConfigDetail,
  DeviceConfigSummary,
  LibraryExport,
  PlaybackEvent,
  PlaybackEventCreate,
  QueueRun,
  RatingFactor,
  RunSummary,
  StatsSummary,
  Track
} from "./types";
import type { YouTubeConfig } from "./youtube";

// A "sitting" id for this app session, attached to ratings so the backend can detect and
// correct a uniformly generous/grumpy mood across one continuous burst of rating.
const ratingSessionId =
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `sit-${Date.now()}-${Math.random().toString(36).slice(2)}`;

const ACTIVE_CONFIG_KEY = "harmonica.activeConfig";

/** Identify the active profile on every request so its library + listening data stay private.
 * A signed bearer token (from create/claim) is tamper-proof; the raw id header is a fallback.
 * No active profile → no header → legacy/local whole-library mode. */
function authHeaders(): Record<string, string> {
  try {
    const raw = localStorage.getItem(ACTIVE_CONFIG_KEY);
    if (!raw) return {};
    const config = JSON.parse(raw) as { id?: number; token?: string | null };
    if (config?.token) return { Authorization: `Bearer ${config.token}` };
    if (typeof config?.id === "number") return { "X-Harmonica-Config-Id": String(config.id) };
  } catch {
    // ignore malformed storage — fall back to local mode
  }
  return {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
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
  // Reports only whether YouTube playback is enabled and whether an optional Data API key is
  // present. This hits the Harmonica backend, never YouTube. No request goes to YouTube until
  // the user turns the feature on and accepts the consent gate.
  youtubeConfig: () => request<YouTubeConfig>("/youtube/config"),
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
        clip_start_seconds: track.clip_start_seconds ?? null,
        clip_end_seconds: track.clip_end_seconds ?? null,
        audio_only: track.audio_only ?? false,
        is_original_rendition: track.is_original_rendition ?? false,
        favourite: track.favourite ?? false,
        groups: track.groups.map((group) => ({
          name: group.name,
          group_type: group.group_type,
          share: group.share ?? null
        })),
        cooldown_tags: track.cooldown_tags,
        // A known video id round-trips as provider+id; a raw pasted URL is sent alone for the
        // backend to parse. An empty list clears the embed.
        embeds: (track.embeds ?? []).map((embed) =>
          embed.external_id
            ? {
                provider: embed.provider,
                external_id: embed.external_id,
                url: embed.url ?? null,
                start_seconds: embed.start_seconds ?? null
              }
            : { url: embed.url ?? null }
        )
        // Ratings are NOT sent here: each is a discrete tap recorded via updateTrackFields,
        // so the bulk metadata save can't re-record the displayed average as a fake rating.
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
  generateQueue: (length: number, seed?: string, configId?: number | null) =>
    request<QueueRun>("/queue/generate", {
      method: "POST",
      body: JSON.stringify({
        length,
        seed: seed || null,
        explain: true,
        ui_active: true,
        config_id: configId ?? null
      })
    }),
  recordPlaybackEvent: (event: PlaybackEventCreate) =>
    request("/playback-events", {
      method: "POST",
      body: JSON.stringify(event)
    }),
  playbackEvents: (limit = 200) =>
    request<PlaybackEvent[]>(`/playback-events?limit=${limit}`),
  getRun: (id: number) => request<QueueRun>(`/playlist-runs/${id}`),
  // --- Cover A/B comparison (Phase E; only active when two-level covers are enabled). ---
  // Returns the next pair to play head-to-head, or null when the set isn't eligible/has settled.
  nextCoverComparison: (subGroup: string) =>
    request<CoverComparisonPair | null>(
      `/cover-comparisons/next?sub_group=${encodeURIComponent(subGroup)}`
    ),
  submitCoverVerdict: (verdict: CoverVerdict) =>
    request("/cover-verdicts", { method: "POST", body: JSON.stringify(verdict) }),
  coverSet: (subGroup: string) =>
    request<CoverSetRead>(`/cover-sets/${encodeURIComponent(subGroup)}`),
  reopenCoverSet: (subGroup: string) =>
    request<CoverSetRead>(`/cover-sets/${encodeURIComponent(subGroup)}/reopen`, { method: "POST" }),
  // Saved-queue endpoints are additive on the backend; callers should tolerate 404.
  listRuns: (limit = 50) => request<RunSummary[]>(`/playlist-runs?limit=${limit}`),
  renameRun: (id: number, name: string) =>
    request<RunSummary>(`/playlist-runs/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name })
    }),
  deleteRun: (id: number) =>
    fetch(`/playlist-runs/${id}`, { method: "DELETE", headers: authHeaders() }).then(
      (response) => {
        if (!response.ok && response.status !== 404) {
          throw new Error(`Delete failed: ${response.status}`);
        }
      }
    ),
  updateTrackFields: (id: number, fields: Record<string, unknown>) =>
    request<Track>(`/tracks/${id}`, {
      method: "PATCH",
      // Tag rating edits with the sitting id (ignored by the backend when no ratings change).
      body: JSON.stringify({ ...fields, rating_session_id: ratingSessionId })
    }),
  exportLibrary: () => request<LibraryExport>("/library/export-json"),
  importLibrary: (payload: LibraryExport) =>
    request<{ ok: boolean }>("/library/import-json", {
      method: "POST",
      body: JSON.stringify({ payload })
    }),
  // --- Device profiles (optional multi-device scope; safe to ignore in local use) ---
  listConfigs: () => request<DeviceConfigSummary[]>("/configs"),
  createConfig: (body: {
    name: string;
    passphrase: string;
    settings?: Record<string, number | boolean>;
    track_ids?: number[];
  }) =>
    request<DeviceConfigDetail>("/configs", {
      method: "POST",
      body: JSON.stringify({
        name: body.name,
        passphrase: body.passphrase,
        settings: body.settings ?? {},
        track_ids: body.track_ids ?? []
      })
    }),
  claimConfig: (name: string, passphrase: string) =>
    request<DeviceConfigDetail>("/configs/claim", {
      method: "POST",
      body: JSON.stringify({ name, passphrase })
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

/** True when the device-profiles backend endpoints are available. */
export async function configsSupported(): Promise<boolean> {
  try {
    await api.listConfigs();
    return true;
  } catch {
    return false;
  }
}
