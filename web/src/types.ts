export type MediaAsset = {
  id: number;
  file_path: string;
  asset_type: "audio" | "video" | string;
  codec?: string | null;
  container?: string | null;
  source?: string | null;
  source_quality?: string | null;
  is_lossless?: boolean | null;
  checksum?: string | null;
  browser_supported: boolean;
};

export type TrackGroup = {
  id: number;
  name: string;
  group_type: string;
  share?: number | null;
};

export type Track = {
  id: number;
  song_id: string;
  title: string;
  artist?: string | null;
  album?: string | null;
  has_lyrics: boolean;
  sub_group?: string | null;
  manual_multiplier: number;
  clip_start_seconds?: number | null;
  clip_end_seconds?: number | null;
  audio_only?: boolean;
  assets: MediaAsset[];
  groups: TrackGroup[];
  cooldown_tags: string[];
  ratings: Record<string, number | null>;
};

export type RatingFactor = {
  id: number;
  key: string;
  label: string;
  weight: number;
  applies_to_lyrics: boolean;
  applies_to_instrumental: boolean;
  applies_to_variants_only: boolean;
  enabled: boolean;
};

export type QueueItem = {
  position: number;
  track: Track;
  media_asset_id?: number | null;
  media_url?: string | null;
  score: number;
  explanation: Record<string, unknown>;
};

export type QueueRun = {
  id: number;
  seed?: string | null;
  length: number;
  items: QueueItem[];
};

export type SettingControl = {
  key: keyof Pick<
    AppSettings,
    | "beta"
    | "group_cooldown_floor"
    | "sub_group_cooldown_floor"
    | "song_rating_min_multiplier"
    | "song_rating_max_multiplier"
    | "enable_group_rating_multiplier"
    | "default_playlist_length"
    | "history_influence_enabled"
    | "skip_penalty_strength"
    | "cold_start_enabled"
    | "cold_start_unrated_boost"
    | "visual_priority_enabled"
    | "visual_priority_multiplier"
    | "group_clustering_bias"
  >;
  label: string;
  description: string;
  value_type: "number" | "boolean";
  control: "slider" | "stepper" | "switch";
  default: number | boolean;
  minimum?: number | null;
  maximum?: number | null;
  step?: number | null;
  unit?: string | null;
  value: number | boolean;
};

export type AppSettings = {
  beta: number;
  group_cooldown_floor: number;
  sub_group_cooldown_floor: number;
  song_rating_min_multiplier: number;
  song_rating_max_multiplier: number;
  enable_group_rating_multiplier: boolean;
  home: string;
  host: string;
  port: number;
  default_playlist_length: number;
  group_rating_min_multiplier: number;
  group_rating_max_multiplier: number;
  history_influence_enabled: boolean;
  skip_penalty_strength: number;
  cold_start_enabled: boolean;
  cold_start_unrated_boost: number;
  visual_priority_enabled: boolean;
  visual_priority_multiplier: number;
  group_clustering_bias: number;
  controls: SettingControl[];
};

export type PlaybackEventCreate = {
  event_type: "started" | "paused" | "skipped" | "completed";
  track_id: number;
  media_asset_id?: number | null;
  playlist_run_id?: number | null;
  queue_position?: number | null;
  progress_seconds?: number | null;
  duration_seconds?: number | null;
};

export type StatsSummary = {
  track_count: number;
  rated_track_count: number;
  unrated_track_count: number;
  video_track_count: number;
  group_count: number;
  playback_event_count: number;
  completed_count: number;
  skipped_count: number;
  early_skip_count: number;
  partial_skip_count: number;
};

export type PlaybackEvent = {
  id: number;
  event_type: "started" | "paused" | "skipped" | "completed" | string;
  track_id: number;
  media_asset_id?: number | null;
  playlist_run_id?: number | null;
  queue_position?: number | null;
  progress_seconds?: number | null;
  duration_seconds?: number | null;
  created_at: string;
};

// Summary of a saved/persisted playlist run (GET /playlist-runs).
// Backend support is additive; the UI degrades gracefully if absent.
export type RunSummary = {
  id: number;
  name?: string | null;
  seed?: string | null;
  length: number;
  item_count: number;
  created_at: string;
  preview_titles: string[];
};

// A plain-language reason describing why a track was queued.
export type WhyReason = {
  icon: "group" | "star" | "spark" | "video" | "cooldown" | "history" | "variant";
  text: string;
  tone: "boost" | "suppress" | "neutral";
};

// Library export/import payloads (GET/POST /library/*-json), used by the
// curation review workflow.
export type LibraryGroupRef = { name: string; group_type: string; share?: number | null };

export type LibraryTrackPayload = {
  song_id: string;
  title: string;
  artist?: string | null;
  album?: string | null;
  has_lyrics: boolean;
  sub_group?: string | null;
  manual_multiplier: number;
  groups: LibraryGroupRef[];
  cooldown_tags: string[];
  ratings: Record<string, number | null>;
  assets?: unknown[];
};

export type LibraryExport = {
  rating_factors?: unknown[];
  groups?: { name: string; group_type: string; manual_multiplier?: number; rating_multiplier?: number }[];
  tracks: LibraryTrackPayload[];
};
