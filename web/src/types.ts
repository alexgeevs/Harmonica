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

// A third-party playback embed (currently only YouTube). Mirrors the backend EmbedRead schema.
export type Embed = {
  id: number;
  provider: string;
  external_id: string;
  url?: string | null;
  start_seconds?: number | null;
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
  is_original_rendition?: boolean;
  favourite?: boolean;
  embeds?: Embed[];
  assets: MediaAsset[];
  groups: TrackGroup[];
  cooldown_tags: string[];
  ratings: Record<string, number | null>;
  // Normalised effective rating per factor (algorithm view); raw stars stay in `ratings`.
  ratings_effective?: Record<string, number | null>;
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
    | "avoid_consecutive_compressed"
    | "compressed_break_reminder"
    | "loudness_warning_enabled"
    | "loudness_warning_level"
    | "rating_normalization_enabled"
    | "rating_outlier_sd"
    | "rating_session_mood_correction"
    | "rating_session_min_songs"
    | "rating_coverage_ready_fraction"
    | "rating_calibration_enabled"
    | "satiation_enabled"
    | "satiation_strength"
    | "satiation_window_days"
    | "rediscovery_enabled"
    | "rediscovery_strength"
    | "rediscovery_halflife_days"
    | "favourite_pacing_enabled"
    | "favourite_pacing_strength"
    | "why_show_math"
    | "cover_two_level_enabled"
    | "cover_count_log_base"
    | "cover_original_bonus"
    | "youtube_embed_enabled"
    | "spotify_enabled"
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
  avoid_consecutive_compressed: boolean;
  compressed_break_reminder: boolean;
  loudness_warning_enabled: boolean;
  loudness_warning_level: number;
  rating_normalization_enabled: boolean;
  rating_outlier_sd: number;
  rating_session_mood_correction: boolean;
  rating_session_min_songs: number;
  rating_coverage_ready_fraction: number;
  rating_calibration_enabled: boolean;
  satiation_enabled: boolean;
  satiation_strength: number;
  satiation_window_days: number;
  rediscovery_enabled: boolean;
  rediscovery_strength: number;
  rediscovery_halflife_days: number;
  favourite_pacing_enabled: boolean;
  favourite_pacing_strength: number;
  why_show_math: boolean;
  cover_two_level_enabled: boolean;
  cover_count_log_base: number;
  cover_original_bonus: number;
  youtube_embed_enabled: boolean;
  spotify_enabled: boolean;
  profile_song_picker_enabled: boolean;
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
  avg_level?: number | null;
  peak_level?: number | null;
  output_gain?: number | null;
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
  avg_level?: number | null;
  peak_level?: number | null;
  output_gain?: number | null;
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

// Cover A/B comparison (Phase E). When two renditions are spliced into the queue for a head-to-head,
// each carries this metadata inside its explanation under the `comparison` key.
export type CoverComparisonMeta = {
  set_id: string;
  role: "a" | "b";
  peer_track_id: number;
};

export type CoverComparisonPair = {
  sub_group: string;
  a: QueueItem;
  b: QueueItem;
};

export type CoverRenditionRead = {
  track_id: number;
  sub_group: string;
  bt_strength: number;
  comparison_count: number;
};

export type CoverSetRead = {
  sub_group: string;
  comparison_phase: "stars" | "bootstrapping" | "settled" | string;
  total_comparisons: number;
  renditions: CoverRenditionRead[];
};

export type CoverVerdict = {
  sub_group: string;
  track_a_id: number;
  track_b_id: number;
  winner_track_id: number | null;
  pct_a?: number | null;
  pct_b?: number | null;
  session_id?: string | null;
  run_id?: number | null;
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

export type LibraryEmbedRef = {
  provider: string;
  external_id?: string | null;
  url?: string | null;
  start_seconds?: number | null;
};

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
  embeds?: LibraryEmbedRef[];
};

export type LibraryExport = {
  rating_factors?: unknown[];
  groups?: { name: string; group_type: string; manual_multiplier?: number; rating_multiplier?: number }[];
  tracks: LibraryTrackPayload[];
};

// Device profiles (optional, multi-device). A profile = which songs are included
// + a settings snapshot, claimable on any device by name + passphrase. Local-only
// use never needs one; activeConfig === null means "full library, global settings".
export type DeviceConfigSummary = {
  id: number;
  name: string;
  track_count: number;
  created_at: string;
};

export type DeviceConfigDetail = {
  id: number;
  name: string;
  settings: Record<string, number | boolean>;
  included_track_ids: number[];
  // Signed bearer token returned on create/claim; the client stores it and sends it as
  // `Authorization: Bearer` so this profile's data stays private and tamper-proof.
  token?: string | null;
};
