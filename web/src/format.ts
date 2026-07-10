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
 * Turn the algorithm's score breakdown into at most three plain-language lines: where the
 * pick came from, the single strongest boost, and the single strongest damper. One of each,
 * so the lines never overlap or contradict each other.
 */
export function whyReasons(item: QueueItem | null): WhyReason[] {
  if (!item) {
    return [];
  }
  const ex = item.explanation ?? {};
  const reasons: WhyReason[] = [];

  // 1. Where it came from.
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

  // 2. The single strongest boost: the multiplier that raised this pick's odds the most.
  type Candidate = { weight: number; icon: WhyReason["icon"]; text: string };
  const boosts: Candidate[] = [];
  const rating = metricNumber(ex.rating_multiplier);
  if (rating >= 1.15) {
    boosts.push({ weight: rating, icon: "star", text: "You rate this highly" });
  }
  const rediscovery = metricNumber(ex.rediscovery_multiplier);
  if (rediscovery > 1.02) {
    boosts.push({
      weight: rediscovery,
      icon: "spark",
      text: "A favourite you haven't heard in a while"
    });
  }
  const coldStart = metricNumber(ex.cold_start_multiplier);
  if (coldStart > 1.01) {
    boosts.push({
      weight: coldStart,
      icon: "spark",
      text: "New to you, surfaced early so you can rate it"
    });
  }
  const nCovers = metricNumber(ex.n_covers, 1);
  if (nCovers > 1 && metricNumber(ex.original_prior, 1) > 1.001) {
    boosts.push({
      weight: metricNumber(ex.original_prior, 1),
      icon: "variant",
      text: `The original recording, out of ${nCovers} versions`
    });
  } else if (nCovers > 1 && metricNumber(ex.cover_performance, 1) > 1.05) {
    boosts.push({
      weight: metricNumber(ex.cover_performance, 1),
      icon: "variant",
      text: `Your favourite of ${nCovers} versions`
    });
  }
  const visual = metricNumber(ex.visual_multiplier);
  if (visual > 1.01) {
    boosts.push({ weight: visual, icon: "video", text: "Has a video, easier to rate on screen" });
  }
  boosts.sort((a, b) => b.weight - a.weight);
  if (boosts[0]) {
    reasons.push({ icon: boosts[0].icon, tone: "boost", text: boosts[0].text });
  }

  // 3. The single strongest damper. Dampers lower a song's odds, they never block it, so a
  // damped song still plays sometimes. The phrasing says "less often", not "resting", because
  // this song was in fact picked.
  const dampers: Candidate[] = [];
  if (rating <= 0.85) {
    dampers.push({ weight: rating, icon: "star", text: "you rate it lower than most" });
  }
  const satiation = metricNumber(ex.satiation_multiplier);
  if (satiation <= 0.92) {
    dampers.push({ weight: satiation, icon: "cooldown", text: "it has had a lot of play lately" });
  }
  const songCooldown = metricNumber(ex.song_cooldown);
  if (songCooldown <= 0.6) {
    dampers.push({ weight: songCooldown, icon: "cooldown", text: "you heard it recently" });
  }
  const history = metricNumber(ex.history_multiplier);
  if (history <= 0.95) {
    dampers.push({ weight: history, icon: "history", text: "you skipped it recently" });
  }
  const subCooldown = metricNumber(ex.sub_group_cooldown);
  if (subCooldown <= 0.6) {
    dampers.push({
      weight: subCooldown,
      icon: "variant",
      text: "another version of it played recently"
    });
  }
  const cooledGroup = groups
    .filter((g) => g.name && typeof g.cooldown === "number")
    .sort((a, b) => metricNumber(a.cooldown, 1) - metricNumber(b.cooldown, 1))[0];
  if (cooledGroup?.name && metricNumber(cooledGroup.cooldown, 1) <= 0.5) {
    dampers.push({
      weight: metricNumber(cooledGroup.cooldown, 1),
      icon: "cooldown",
      text: `${cooledGroup.name} has played a lot recently`
    });
  }
  dampers.sort((a, b) => a.weight - b.weight);
  if (dampers[0]) {
    reasons.push({
      icon: dampers[0].icon,
      tone: "suppress",
      text: `Coming up less often right now: ${dampers[0].text}`
    });
  }

  if (reasons.length === 0) {
    reasons.push({ icon: "group", tone: "neutral", text: "A balanced pick for variety" });
  }
  return reasons;
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
  { key: "song_cooldown", label: "Heard recently" },
  { key: "sub_group_cooldown", label: "Version heard recently" }
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
