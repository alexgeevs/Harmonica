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
    reasons.push({ icon: "star", tone: "boost", text: `You rate this highly (×${rating.toFixed(2)})` });
  } else if (rating <= 0.85) {
    reasons.push({
      icon: "star",
      tone: "suppress",
      text: `Rated lower than average, so it comes up less (×${rating.toFixed(2)})`
    });
  }

  const coldStart = metricNumber(ex.cold_start_multiplier);
  if (coldStart > 1.01) {
    reasons.push({
      icon: "spark",
      tone: "boost",
      text: "New to you — surfaced early so you can rate it"
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

export function pct(part: number, whole: number): number {
  if (whole <= 0) {
    return 0;
  }
  return Math.round((part / whole) * 100);
}
