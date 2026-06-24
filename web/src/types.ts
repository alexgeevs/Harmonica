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
};

