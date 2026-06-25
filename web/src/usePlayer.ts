import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { QueueItem, QueueRun } from "./types";

const SESSION_KEY = "harmonica.session.v1";
const VOLUME_KEY = "harmonica.volume.v1";

type StoredSession = {
  runId: number | null;
  index: number;
  currentTime: number;
  queue: QueueItem[];
};

type PlaybackEventType = "started" | "paused" | "skipped" | "completed";

function loadSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as StoredSession;
    if (!Array.isArray(parsed.queue)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function loadVolume(): number {
  const raw = Number(localStorage.getItem(VOLUME_KEY));
  return Number.isFinite(raw) && raw >= 0 && raw <= 1 ? raw : 1;
}

/**
 * App-wide audio engine. Owns a single HTMLAudioElement so playback continues
 * across view changes, autoplays through the queue, records history events with
 * Harmonica's skip semantics, and persists the listening session across refresh.
 */
export function usePlayer() {
  // A <video> element (not <audio>) so visual tracks can be watched; it plays
  // audio-only sources just as well. It is reparented across views by the app
  // shell so playback never stops when you switch screens.
  const audioRef = useRef<HTMLVideoElement | null>(null);
  if (audioRef.current === null && typeof document !== "undefined") {
    const element = document.createElement("video");
    element.preload = "metadata";
    element.setAttribute("playsinline", "");
    audioRef.current = element;
  }

  const restored = useRef<StoredSession | null>(loadSession());
  const [queue, setQueue] = useState<QueueItem[]>(restored.current?.queue ?? []);
  const [index, setIndex] = useState<number>(restored.current?.index ?? 0);
  const [runId, setRunId] = useState<number | null>(restored.current?.runId ?? null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(restored.current?.currentTime ?? 0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState<number>(loadVolume());
  const [muted, setMuted] = useState(false);

  // Refs mirror state so the once-bound audio listeners never read stale values.
  const queueRef = useRef(queue);
  const indexRef = useRef(index);
  const runIdRef = useRef(runId);
  const wantsPlayRef = useRef(false);
  const pendingSeekRef = useRef<number>(restored.current?.currentTime ?? 0);
  const startedKeyRef = useRef<string | null>(null);
  queueRef.current = queue;
  indexRef.current = index;
  runIdRef.current = runId;

  const currentItem = queue[index] ?? null;
  const currentUrl = currentItem?.media_url ?? null;
  const currentKey = currentItem ? itemKey(currentItem) : null;

  const recordEvent = useCallback(
    (type: PlaybackEventType, item: QueueItem | null, progress?: number, dur?: number) => {
      if (!item) {
        return;
      }
      void api
        .recordPlaybackEvent({
          event_type: type,
          track_id: item.track.id,
          media_asset_id: item.media_asset_id ?? null,
          playlist_run_id: runIdRef.current || null,
          queue_position: item.position,
          progress_seconds: Number.isFinite(progress) ? progress ?? null : null,
          duration_seconds: Number.isFinite(dur) ? dur ?? null : null
        })
        .catch(() => {
          /* history is best-effort; never block playback on it */
        });
    },
    []
  );

  const saveSession = useCallback(() => {
    const audio = audioRef.current;
    const payload: StoredSession = {
      runId: runIdRef.current,
      index: indexRef.current,
      currentTime: audio ? audio.currentTime : 0,
      queue: queueRef.current
    };
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
    } catch {
      /* storage may be full or unavailable; non-fatal */
    }
  }, []);

  // Advance to the next item; reason distinguishes a natural finish from a user skip.
  const goToIndex = useCallback(
    (target: number, opts: { recordSkip?: boolean; play?: boolean } = {}) => {
      const audio = audioRef.current;
      const items = queueRef.current;
      if (target < 0 || target >= items.length) {
        if (target >= items.length) {
          wantsPlayRef.current = false;
          audio?.pause();
        }
        return;
      }
      if (opts.recordSkip && audio) {
        const leaving = items[indexRef.current];
        recordEvent("skipped", leaving, audio.currentTime, audio.duration);
      }
      pendingSeekRef.current = 0;
      wantsPlayRef.current = opts.play ?? wantsPlayRef.current;
      setIndex(target);
    },
    [recordEvent]
  );

  // Bind audio element listeners exactly once.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.volume = volume;

    const onTime = () => setCurrentTime(audio.currentTime);
    const onMeta = () => setDuration(audio.duration || 0);
    const onPlay = () => {
      setIsPlaying(true);
      const item = queueRef.current[indexRef.current] ?? null;
      const key = item ? itemKey(item) : null;
      if (item && key !== startedKeyRef.current) {
        startedKeyRef.current = key;
        recordEvent("started", item, audio.currentTime, audio.duration);
      }
    };
    const onPause = () => {
      setIsPlaying(false);
      const item = queueRef.current[indexRef.current] ?? null;
      // Ignore the pause that fires right at end-of-track (handled by onEnded).
      if (item && audio.currentTime < (audio.duration || Infinity) - 0.4) {
        recordEvent("paused", item, audio.currentTime, audio.duration);
      }
      saveSession();
    };
    const onEnded = () => {
      const item = queueRef.current[indexRef.current] ?? null;
      recordEvent("completed", item, audio.duration, audio.duration);
      startedKeyRef.current = null;
      wantsPlayRef.current = true;
      goToIndex(indexRef.current + 1, { play: true });
    };

    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("loadedmetadata", onMeta);
    audio.addEventListener("durationchange", onMeta);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("loadedmetadata", onMeta);
      audio.removeEventListener("durationchange", onMeta);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load the source whenever the *current track* changes (keyed on the track
  // identity, so reordering the queue never reloads the playing track).
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    if (!currentUrl) {
      audio.removeAttribute("src");
      audio.load();
      setCurrentTime(0);
      setDuration(0);
      // Some tracks may have no media yet (e.g. still downloading). When playing
      // forward, jump to the next item that actually has a file rather than stall.
      if (wantsPlayRef.current) {
        const items = queueRef.current;
        let next = indexRef.current + 1;
        while (next < items.length && !items[next]?.media_url) {
          next += 1;
        }
        if (next < items.length) {
          startedKeyRef.current = null;
          setIndex(next);
          return;
        }
        wantsPlayRef.current = false;
      }
      setIsPlaying(false);
      return;
    }
    audio.src = currentUrl;
    audio.load();
    const seekTo = pendingSeekRef.current;
    pendingSeekRef.current = 0;
    const applySeek = () => {
      if (seekTo > 0) {
        try {
          audio.currentTime = seekTo;
        } catch {
          /* metadata not ready yet; ignore */
        }
      }
      audio.removeEventListener("loadedmetadata", applySeek);
    };
    audio.addEventListener("loadedmetadata", applySeek);
    if (wantsPlayRef.current) {
      void audio.play().catch(() => setIsPlaying(false));
    }
    return () => audio.removeEventListener("loadedmetadata", applySeek);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentKey]);

  // Persist the session whenever its durable parts change, and on a slow heartbeat.
  useEffect(() => {
    saveSession();
  }, [queue, index, runId, saveSession]);

  useEffect(() => {
    const onLeave = () => saveSession();
    window.addEventListener("beforeunload", onLeave);
    document.addEventListener("visibilitychange", onLeave);
    const heartbeat = window.setInterval(saveSession, 5000);
    return () => {
      window.removeEventListener("beforeunload", onLeave);
      document.removeEventListener("visibilitychange", onLeave);
      window.clearInterval(heartbeat);
    };
  }, [saveSession]);

  // --- Controls -------------------------------------------------------------
  const loadQueue = useCallback((run: QueueRun, opts: { autoplay?: boolean } = {}) => {
    pendingSeekRef.current = 0;
    startedKeyRef.current = null;
    wantsPlayRef.current = opts.autoplay ?? true;
    setQueue(run.items);
    setRunId(run.id || null);
    setIndex(0);
  }, []);

  const playAt = useCallback(
    (target: number) => {
      const sameTrack = target === indexRef.current;
      wantsPlayRef.current = true;
      if (sameTrack) {
        void audioRef.current?.play().catch(() => setIsPlaying(false));
        return;
      }
      goToIndex(target, { recordSkip: true, play: true });
    },
    [goToIndex]
  );

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !currentUrl) {
      return;
    }
    if (audio.paused) {
      wantsPlayRef.current = true;
      void audio.play().catch(() => setIsPlaying(false));
    } else {
      wantsPlayRef.current = false;
      audio.pause();
    }
  }, [currentUrl]);

  const next = useCallback(() => goToIndex(indexRef.current + 1, { recordSkip: true, play: true }), [
    goToIndex
  ]);

  const previous = useCallback(() => {
    const audio = audioRef.current;
    // Spotify-style: restart the track if we're more than 3s in, else go back one.
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    goToIndex(indexRef.current - 1, { play: true });
  }, [goToIndex]);

  const seek = useCallback((seconds: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = seconds;
      setCurrentTime(seconds);
    }
  }, []);

  const setVolume = useCallback((value: number) => {
    const clamped = Math.min(Math.max(value, 0), 1);
    setVolumeState(clamped);
    setMuted(clamped === 0);
    if (audioRef.current) {
      audioRef.current.volume = clamped;
      audioRef.current.muted = false;
    }
    try {
      localStorage.setItem(VOLUME_KEY, String(clamped));
    } catch {
      /* ignore */
    }
  }, []);

  const toggleMute = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    const nextMuted = !audio.muted;
    audio.muted = nextMuted;
    setMuted(nextMuted);
  }, []);

  const removeAt = useCallback((target: number) => {
    setQueue((current) => {
      if (target < 0 || target >= current.length) {
        return current;
      }
      const activeKey = current[indexRef.current] ? itemKey(current[indexRef.current]) : null;
      const removingActive = target === indexRef.current;
      const updated = current.filter((_, i) => i !== target);
      if (removingActive) {
        const audio = audioRef.current;
        recordEvent("skipped", current[target], audio?.currentTime, audio?.duration);
        // Keep the same slot so the next track slides into place and plays.
        const nextIndex = Math.min(indexRef.current, updated.length - 1);
        pendingSeekRef.current = 0;
        startedKeyRef.current = null;
        setIndex(Math.max(nextIndex, 0));
      } else {
        const newActive = updated.findIndex((item) => itemKey(item) === activeKey);
        if (newActive >= 0) {
          setIndex(newActive);
        }
      }
      return updated;
    });
  }, [recordEvent]);

  const moveItem = useCallback((from: number, to: number) => {
    setQueue((current) => {
      if (
        from < 0 ||
        to < 0 ||
        from >= current.length ||
        to >= current.length ||
        from === to
      ) {
        return current;
      }
      const activeKey = current[indexRef.current] ? itemKey(current[indexRef.current]) : null;
      const updated = [...current];
      const [moved] = updated.splice(from, 1);
      updated.splice(to, 0, moved);
      const newActive = updated.findIndex((item) => itemKey(item) === activeKey);
      if (newActive >= 0) {
        setIndex(newActive);
      }
      return updated;
    });
  }, []);

  const clear = useCallback(() => {
    wantsPlayRef.current = false;
    startedKeyRef.current = null;
    audioRef.current?.pause();
    setQueue([]);
    setIndex(0);
    setRunId(null);
    try {
      localStorage.removeItem(SESSION_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  return useMemo(
    () => ({
      mediaEl: audioRef.current,
      queue,
      index,
      currentItem,
      currentKey,
      runId,
      isPlaying,
      currentTime,
      duration,
      volume,
      muted,
      loadQueue,
      playAt,
      togglePlay,
      next,
      previous,
      seek,
      setVolume,
      toggleMute,
      removeAt,
      moveItem,
      clear
    }),
    [
      queue,
      index,
      currentItem,
      currentKey,
      runId,
      isPlaying,
      currentTime,
      duration,
      volume,
      muted,
      loadQueue,
      playAt,
      togglePlay,
      next,
      previous,
      seek,
      setVolume,
      toggleMute,
      removeAt,
      moveItem,
      clear
    ]
  );
}

export type PlayerApi = ReturnType<typeof usePlayer>;

function itemKey(item: QueueItem): string {
  return `${item.position}:${item.track.id}`;
}
