// Listening presets: each applies a bundle of values to the existing algorithm
// settings (PATCH /settings). The design axis is grounded in how streaming
// recommenders trade short-run engagement (familiarity, repeat-listens, keeping
// similar things together) against long-term satisfaction (diversity, avoiding
// overplay fatigue and artist/album bubbles).
//
// Knob intuition for Harmonica's algorithm:
//   - group_cooldown_floor / sub_group_cooldown_floor: HIGHER floor = a
//     just-played group/variant recovers fast = MORE repetition. LOWER = stronger
//     anti-repeat.
//   - group_clustering_bias: +ve encourages consecutive same-group runs (listen
//     through a musical); -ve enforces variety (no back-to-back same source).
//   - skip_penalty_strength: how hard a skipped track is suppressed next time.
//   - cold_start_*: deliberate coverage of unheard/unrated tracks.
//   - beta: how strongly larger groups out-weigh smaller ones (sublinear).

export type PresetValues = Record<string, number | boolean>;

export type Preset = {
  key: string;
  name: string;
  tagline: string;
  description: string;
  values: PresetValues;
};

export const PRESETS: Preset[] = [
  {
    key: "familiar",
    name: "Familiar",
    tagline: "Comfort & favourites",
    description:
      "Leans into what you already love — replays favourites sooner, keeps similar songs together, and skips the friction. The streaming-style 'keep me in my lane' feel.",
    values: {
      beta: 1.5,
      group_cooldown_floor: 0.3,
      sub_group_cooldown_floor: 0.08,
      song_rating_min_multiplier: 0.6,
      song_rating_max_multiplier: 2.0,
      enable_group_rating_multiplier: true,
      history_influence_enabled: true,
      skip_penalty_strength: 0.15,
      cold_start_enabled: false,
      cold_start_unrated_boost: 1.5,
      visual_priority_enabled: true,
      visual_priority_multiplier: 1.2,
      group_clustering_bias: 0.35
    }
  },
  {
    key: "balanced",
    name: "Balanced",
    tagline: "The default blend",
    description:
      "Harmonica's sensible default: rewards what you rate highly while steadily cooling down anything you've heard recently.",
    values: {
      beta: 1.25,
      group_cooldown_floor: 0.05,
      sub_group_cooldown_floor: 0.01,
      song_rating_min_multiplier: 0.5,
      song_rating_max_multiplier: 2.0,
      enable_group_rating_multiplier: true,
      history_influence_enabled: true,
      skip_penalty_strength: 0.25,
      cold_start_enabled: true,
      cold_start_unrated_boost: 2.0,
      visual_priority_enabled: true,
      visual_priority_multiplier: 1.35,
      group_clustering_bias: 0.0
    }
  },
  {
    key: "discovery",
    name: "Discovery",
    tagline: "Give everything a chance",
    description:
      "Pushes unheard and unrated tracks to the front and stops big groups from dominating, so the whole library gets fair coverage. Best while you're still rating things.",
    values: {
      beta: 0.9,
      group_cooldown_floor: 0.05,
      sub_group_cooldown_floor: 0.01,
      song_rating_min_multiplier: 0.7,
      song_rating_max_multiplier: 1.6,
      enable_group_rating_multiplier: true,
      history_influence_enabled: true,
      skip_penalty_strength: 0.25,
      cold_start_enabled: true,
      cold_start_unrated_boost: 3.0,
      visual_priority_enabled: true,
      visual_priority_multiplier: 1.6,
      group_clustering_bias: -0.2
    }
  },
  {
    key: "long_game",
    name: "Long game",
    tagline: "Never wear a song out",
    description:
      "Maximises long-term enjoyment by punishing repetition hard — a song you just heard is strongly held back, and variety across artists and sources is enforced.",
    values: {
      beta: 1.1,
      group_cooldown_floor: 0.02,
      sub_group_cooldown_floor: 0.005,
      song_rating_min_multiplier: 0.5,
      song_rating_max_multiplier: 1.8,
      enable_group_rating_multiplier: true,
      history_influence_enabled: true,
      skip_penalty_strength: 0.5,
      cold_start_enabled: true,
      cold_start_unrated_boost: 2.0,
      visual_priority_enabled: true,
      visual_priority_multiplier: 1.35,
      group_clustering_bias: -0.6
    }
  }
];

/** Returns the preset whose values all match the current settings, if any. */
export function matchPreset(current: Record<string, number | boolean>): string | null {
  for (const preset of PRESETS) {
    const matches = Object.entries(preset.values).every(([key, value]) => {
      const actual = current[key];
      if (typeof value === "number" && typeof actual === "number") {
        return Math.abs(actual - value) < 1e-6;
      }
      return actual === value;
    });
    if (matches) {
      return preset.key;
    }
  }
  return null;
}
