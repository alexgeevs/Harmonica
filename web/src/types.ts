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
