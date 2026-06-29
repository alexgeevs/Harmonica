import type { QueueItem, Track, WhyReason } from "./types";

export function formatTime(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) {
    return "0:00";
  }
  const total = Math.floor(seconds);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function displayArtist(track?: Track | null): string {
  if (!track) {
    return "";
  }
  return [track.artist, track.album].filter(Boolean).join(" · ");
}

export function metricNumber(value: unknown, fallback = 1): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

type GroupContribution = {
  name?: string;
  size?: number;
  contribution?: number;
  cooldown?: number;
  group_type?: string;
};

/**
 * Turn the algorithm's score breakdown into a handful of plain-language reasons a
 * listener can actually read. Ordered most-salient first, capped to keep it calm.
 */
export function whyReasons(item: QueueItem | null): WhyReason[] {
  if (!item) {
    return [];
  }
  const ex = item.explanation ?? {};
  const reasons: WhyReason[] = [];

  const groups = Array.isArray(ex.group_contributions)
    ? ([...ex.group_contributions] as GroupContribution[])
    : [];
  groups.sort((a, b) => metricNumber(b.contribution, 0) - metricNumber(a.contribution, 0));
  const topGroup = groups[0];
  if (topGroup?.name) {
    const size = metricNumber(topGroup.size, 0);
    const sizeText = size > 0 ? ` (${size} track${size === 1 ? "" : "s"})` : "";
    reasons.push({
      icon: "group",
      tone: "neutral",
      text: `Drawn from ${topGroup.name}${sizeText}`
    });
  }

  const rating = metricNumber(ex.rating_multiplier);
  if (rating >= 1.15) {
    reasons.push({ icon: "star", tone: "boost", text: "You rate this highly" });
  } else if (rating <= 0.85) {
    reasons.push({
      icon: "star",
      tone: "suppress",
      text: "You rate this lower than most, so it comes up less often"
    });
  }

  // A dormant favourite being brought back fresh — directly serves the binge-then-rest pattern.
  const rediscovery = metricNumber(ex.rediscovery_multiplier);
  if (rediscovery > 1.02) {
    reasons.push({
      icon: "spark",
      tone: "boost",
      text: "A favourite you haven't heard in a while — bringing it back fresh"
    });
  }

  // Two-level cover selection: which song, then which rendition.
  const nCovers = metricNumber(ex.n_covers, 1);
  if (nCovers > 1) {
    reasons.push({
      icon: "variant",
      tone: "neutral",
      text: `One of ${nCovers} versions of this song`
    });
    if (metricNumber(ex.original_prior, 1) > 1.001) {
      reasons.push({ icon: "star", tone: "boost", text: "The original recording" });
    } else if (metricNumber(ex.cover_performance, 1) > 1.05) {
      reasons.push({ icon: "star", tone: "boost", text: "Your favourite rendition of it" });
    }
  }

  const coldStart = metricNumber(ex.cold_start_multiplier);
  if (coldStart > 1.01) {
    reasons.push({
      icon: "spark",
      tone: "boost",
      text: "New to you — surfaced early so you can rate it"
    });
  }

  // Satiation: eased off because you've been playing it a lot lately (avoid burning it out).
  const satiation = metricNumber(ex.satiation_multiplier);
  if (satiation <= 0.92) {
    reasons.push({
      icon: "cooldown",
      tone: "suppress",
      text: "You've played this a lot lately — resting it so it doesn't wear out"
    });
  }

  // The single highest-trust anti-repetition message: you literally just heard this song.
  const songCooldown = metricNumber(ex.song_cooldown);
  if (songCooldown <= 0.6) {
    reasons.push({
      icon: "cooldown",
      tone: "suppress",
      text: "You heard this exact song recently"
    });
  }

  // The most-cooled group this track belongs to (e.g. "eased off this artist/source").
  const cooledGroup = groups
    .filter((g) => g.name && typeof g.cooldown === "number")
    .sort((a, b) => metricNumber(a.cooldown, 1) - metricNumber(b.cooldown, 1))[0];
  if (cooledGroup?.name && metricNumber(cooledGroup.cooldown, 1) <= 0.5) {
    reasons.push({
      icon: "cooldown",
      tone: "suppress",
      text: `Eased off ${cooledGroup.name} for variety`
    });
  }

  const visual = metricNumber(ex.visual_multiplier);
  if (visual > 1.01) {
    reasons.push({
      icon: "video",
      tone: "boost",
      text: "Has a video — easier to review while you're here"
    });
  }

  const history = metricNumber(ex.history_multiplier);
  if (history <= 0.95) {
    reasons.push({
      icon: "history",
      tone: "suppress",
      text: "Recently skipped, so it's eased off for now"
    });
  }

  const subCooldown = metricNumber(ex.sub_group_cooldown);
  if (subCooldown <= 0.6) {
    reasons.push({
      icon: "variant",
      tone: "suppress",
      text: "Another version of this song played recently"
    });
  }

  if (reasons.length === 0) {
    reasons.push({ icon: "group", tone: "neutral", text: "A balanced pick for variety" });
  }
  return reasons.slice(0, 4);
}

/** A one-line summary used in compact spots (queue rows, tooltips). */
export function whyHeadline(item: QueueItem | null): string {
  const reasons = whyReasons(item);
  return reasons[0]?.text ?? "";
}

// The full multiplier-by-multiplier maths behind a pick, for the optional "show the maths" view.
// One row per factor in the exact order the algorithm multiplies them, so base × every row = score.
export type WhyMathRow = { label: string; value: number; neutral: boolean };
export type WhyMath = {
  base: number;
  rows: WhyMathRow[];
  score: number;
};

// Factors in product order (mirrors score_track in algorithm.py). base_score is the starting
// value; everything else is a multiplier applied to it.
const MATH_FACTORS: { key: string; label: string }[] = [
  { key: "manual_multiplier", label: "Manual nudge" },
  { key: "rating_multiplier", label: "Your rating" },
  { key: "history_multiplier", label: "Skip history" },
  { key: "cold_start_multiplier", label: "New-song boost" },
  { key: "satiation_multiplier", label: "Played a lot lately" },
  { key: "rediscovery_multiplier", label: "Dormant favourite" },
  { key: "visual_multiplier", label: "Has a video" },
  { key: "song_cooldown", label: "Resting this song" },
  { key: "sub_group_cooldown", label: "Resting this version" }
];

/** Build the numeric breakdown shown when "show the maths" is enabled. Null if no explanation. */
export function whyMath(item: QueueItem | null): WhyMath | null {
  if (!item) {
    return null;
  }
  const ex = item.explanation ?? {};
  if (ex.base_score == null && ex.score == null) {
    return null;
  }
  const base = metricNumber(ex.base_score, 0);
  const rows = MATH_FACTORS.map((factor) => {
    const value = metricNumber((ex as Record<string, unknown>)[factor.key], 1);
    return { label: factor.label, value, neutral: Math.abs(value - 1) < 0.005 };
  });
  return { base, rows, score: metricNumber(ex.score, 0) };
}

export function pct(part: number, whole: number): number {
  if (whole <= 0) {
    return 0;
  }
  return Math.round((part / whole) * 100);
}
