import { useEffect, useRef } from "react";
import { api } from "./api";
import type { CoverComparisonMeta, QueueItem, Track } from "./types";
import type { PlayerApi } from "./usePlayer";

// Mirror of the backend defaults (config.py: cover_active_window / cover_active_min_rated /
// cover_comparison_cooldown_songs). The server is the source of truth for *eligibility*; these only
// gate when the client bothers to ask.
const ACTIVE_WINDOW = 5;
const ACTIVE_MIN_RATED = 4;
const COOLDOWN_SONGS = 3;

/** Read the A/B comparison metadata a spliced item carries in its explanation, if any. */
export function comparisonMeta(item: QueueItem | null | undefined): CoverComparisonMeta | null {
  const meta = item?.explanation?.comparison as CoverComparisonMeta | undefined;
  if (meta && (meta.role === "a" || meta.role === "b") && typeof meta.set_id === "string") {
    return meta;
  }
  return null;
}

function isRated(track: Track | undefined): boolean {
  if (!track) {
    return false;
  }
  return Object.values(track.ratings ?? {}).some((value) => value != null);
}

/**
 * Watches playback and, when the listener is clearly "active" (rating most of what they hear) and
 * lands on a song that belongs to an eligible cover set, asks the server for the next A/B pair and
 * splices the two renditions in to play back-to-back. The actual "which was better?" prompt is the
 * ComparisonCard rendered when the second (role "b") rendition is playing.
 *
 * Entirely inert unless two-level covers are enabled and the set is eligible (server-gated).
 */
export function useCoverComparison(player: PlayerApi, tracks: Track[], enabled: boolean): void {
  const recentRef = useRef<number[]>([]);
  const songsSinceRef = useRef<number>(COOLDOWN_SONGS); // allow the first eligible offer promptly
  const offeredRef = useRef<Set<string>>(new Set());
  const lastIdRef = useRef<number | null>(null);
  const ratedByIdRef = useRef<Map<number, boolean>>(new Map());

  ratedByIdRef.current = new Map(tracks.map((track) => [track.id, isRated(track)]));

  const currentKey = player.currentKey;

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const item = player.currentItem;
    if (!item) {
      return;
    }
    const trackId = item.track.id;
    // Track distinct songs as they surface, for the "active" (4-of-last-5-rated) signal + cooldown.
    if (lastIdRef.current !== trackId) {
      lastIdRef.current = trackId;
      recentRef.current = [...recentRef.current, trackId].slice(-ACTIVE_WINDOW);
      songsSinceRef.current += 1;
    }

    // Don't offer a new comparison while one is already staged/playing.
    if (comparisonMeta(item)) {
      return;
    }
    const subGroup = item.track.sub_group;
    if (!subGroup || offeredRef.current.has(subGroup)) {
      return;
    }
    if (songsSinceRef.current < COOLDOWN_SONGS) {
      return;
    }
    const recent = recentRef.current;
    const ratedCount = recent.filter((id) => ratedByIdRef.current.get(id)).length;
    const active = recent.length >= ACTIVE_MIN_RATED && ratedCount >= ACTIVE_MIN_RATED;
    if (!active) {
      return;
    }

    let cancelled = false;
    offeredRef.current.add(subGroup); // mark immediately so we ask at most once per set per session
    void api
      .nextCoverComparison(subGroup)
      .then((pair) => {
        if (cancelled || !pair || !pair.a || !pair.b) {
          return;
        }
        player.spliceNext([pair.a, pair.b]);
        songsSinceRef.current = 0;
      })
      .catch(() => {
        /* comparison is best-effort; never disturb playback */
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentKey, enabled]);
}
