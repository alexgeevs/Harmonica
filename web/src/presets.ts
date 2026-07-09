// Listening presets: each applies a bundle of values to the algorithm settings (PATCH
// /settings). The design axis is grounded in how streaming recommenders trade short-run
// engagement (familiarity, repeat-listens, keeping similar things together) against long-term
// satisfaction (diversity, avoiding overplay fatigue and artist/album bubbles). Each preset was
// designed and independently reviewed against behavioural-economics reasoning.
//
// Every preset sets the SAME full set of keys, so switching from one to another fully overrides
// the previous one (no knob is left "sticky" at an old preset's value).
//
// Knob intuition for Harmonica's algorithm:
//   - group_cooldown_floor / sub_group_cooldown_floor: HIGHER floor = a just-played group/variant
//     recovers fast = MORE repetition. LOWER = stronger anti-repeat.
//   - group_clustering_bias: +ve encourages consecutive same-group runs (listen through a
//     musical); -ve enforces variety (no back-to-back same source).
//   - skip_penalty_strength: how hard a skipped track is suppressed next time.
//   - cold_start_*: deliberate coverage of unheard/unrated tracks (exploration).
//   - beta: how strongly larger groups out-weigh smaller ones (sublinear).
//   - satiation_*: pace a recently over-played song so a binge doesn't burn it out.
//   - rediscovery_*: resurface a dormant favourite the longer it has gone unheard.
//   - favourite_pacing_*: apply that pacing more firmly to songs tagged as favourites.

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
    tagline: "Comfort and the songs you love",
    description:
      "Leans hard into what you already love. Highly rated songs and the artists and sources you have collected most carry more weight, similar songs stay together in cohesive runs, and unheard or unrated material is kept out of the way. A light touch of pacing still cycles your loved songs so they come back before you forget them and never get played until they wear thin.",
    values: {
      beta: 1.5,
      group_cooldown_floor: 0.35,
      sub_group_cooldown_floor: 0.08,
      song_rating_min_multiplier: 0.5,
      song_rating_max_multiplier: 2.4,
      enable_group_rating_multiplier: true,
      history_influence_enabled: true,
      skip_penalty_strength: 0.15,
      cold_start_enabled: false,
      cold_start_unrated_boost: 1.5,
      visual_priority_enabled: true,
      visual_priority_multiplier: 1.15,
      group_clustering_bias: 0.45,
      satiation_enabled: true,
      satiation_strength: 0.3,
      satiation_window_days: 10,
      rediscovery_enabled: true,
      rediscovery_strength: 0.5,
      rediscovery_halflife_days: 40,
      favourite_pacing_enabled: false,
      favourite_pacing_strength: 1.0
    }
  },
  {
    key: "balanced",
    name: "Balanced",
    tagline: "The sensible everyday default",
    description:
      "The safe everyday choice. It rewards the songs you rate highly and still gives unrated songs a fair hearing, while steadily cooling anything you have played recently. Over the weeks it eases off tracks you have leaned on heavily so they do not wear thin, and it quietly brings long dormant favourites back into rotation. It leans in no direction, so it stays fresh across months of use without favouring comfort or novelty.",
    values: {
      beta: 1.25,
      group_cooldown_floor: 0.15,
      sub_group_cooldown_floor: 0.04,
      song_rating_min_multiplier: 0.5,
      song_rating_max_multiplier: 2.0,
      enable_group_rating_multiplier: true,
      history_influence_enabled: true,
      skip_penalty_strength: 0.3,
      cold_start_enabled: true,
      cold_start_unrated_boost: 2.0,
      visual_priority_enabled: true,
      visual_priority_multiplier: 1.0,
      group_clustering_bias: 0.0,
      satiation_enabled: true,
      satiation_strength: 0.5,
      satiation_window_days: 14,
      rediscovery_enabled: true,
      rediscovery_strength: 0.4,
      rediscovery_halflife_days: 60,
      favourite_pacing_enabled: false,
      favourite_pacing_strength: 1.5
    }
  },
  {
    key: "discovery",
    name: "Discovery",
    tagline: "Give every song a fair hearing",
    description:
      "Pushes unheard and unrated songs to the front and keeps any one artist, source, or theme from taking over, so the whole library gets a fair hearing. Old low ratings are treated gently, because a song you dismissed a year ago may land differently now. Known favourites are held back a little so new material can lead, though a long forgotten favourite will occasionally resurface for a fresh opinion. Best used while you are still rating your library, and worth turning on again every few months to let your ratings catch up with your taste.",
    values: {
      beta: 0.7,
      group_cooldown_floor: 0.04,
      sub_group_cooldown_floor: 0.01,
      song_rating_min_multiplier: 0.85,
      song_rating_max_multiplier: 1.4,
      enable_group_rating_multiplier: false,
      history_influence_enabled: true,
      skip_penalty_strength: 0.1,
      cold_start_enabled: true,
      cold_start_unrated_boost: 4.0,
      visual_priority_enabled: true,
      visual_priority_multiplier: 1.5,
      group_clustering_bias: -0.4,
      satiation_enabled: true,
      satiation_strength: 0.8,
      satiation_window_days: 21,
      rediscovery_enabled: true,
      rediscovery_strength: 0.25,
      rediscovery_halflife_days: 120,
      favourite_pacing_enabled: false,
      favourite_pacing_strength: 1.2
    }
  },
  {
    key: "long_game",
    name: "Long game",
    tagline: "Never wear a song out",
    description:
      "Spreads attention across songs, artists, sources and versions so that favourites keep their value over time. It favours steady exploration, firm repeat spacing and gradual rediscovery rather than short bursts of overplaying. It is built for careful long-term listening, where the best outcome is not hearing your best songs as often as possible now, but still wanting to hear them years from now.",
    values: {
      beta: 0.75,
      group_cooldown_floor: 0.01,
      sub_group_cooldown_floor: 0.0,
      song_rating_min_multiplier: 0.45,
      song_rating_max_multiplier: 1.55,
      enable_group_rating_multiplier: true,
      history_influence_enabled: true,
      skip_penalty_strength: 0.4,
      cold_start_enabled: true,
      cold_start_unrated_boost: 2.4,
      visual_priority_enabled: false,
      visual_priority_multiplier: 1.0,
      group_clustering_bias: -0.75,
      satiation_enabled: true,
      satiation_strength: 1.3,
      satiation_window_days: 30,
      rediscovery_enabled: true,
      rediscovery_strength: 0.3,
      rediscovery_halflife_days: 90,
      favourite_pacing_enabled: true,
      favourite_pacing_strength: 2.0
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
