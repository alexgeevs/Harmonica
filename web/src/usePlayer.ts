import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { QueueItem, QueueRun } from "./types";

const SESSION_KEY = "harmonica.session.v2";
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

// Imperative handles the YouTube (or other external) player registers so the transport
// bar can drive it, since such content plays in its own iframe, not our <video> element.
type ExternalControls = { play: () => void; pause: () => void };

/**
 * App-wide audio engine. Owns a single HTMLAudioElement so playback continues
 * across view changes, autoplays through the queue, records history events with
 * Harmonica's skip semantics, and persists the listening session across refresh.
 *
 * `isExternalItem` marks a queue item that plays through a third-party official player
 * (e.g. a YouTube embed) rather than this <video> element. For those items we park the
 * element and let the embed component drive playback and queue advancement.
 */
export function usePlayer(isExternalItem?: (item: QueueItem) => boolean) {
  // A <video> element (not <audio>) so visual tracks can be watched; it plays
  // audio-only sources just as well. It is reparented across views by the app
  // shell so playback never stops when you switch screens.
  const audioRef = useRef<HTMLVideoElement | null>(null);
  if (audioRef.current === null && typeof document !== "undefined") {
    const element = document.createElement("video");
    element.preload = "metadata";
    element.setAttribute("playsinline", "");
    // Native controls give video tracks fullscreen + scrubbing; they stay in sync
    // with the app transport bar because both act on this same element.
    element.controls = true;
    audioRef.current = element;
  }

  const restored = useRef<StoredSession | null>(loadSession());
  const [queue, setQueue] = useState<QueueItem[]>(restored.current?.queue ?? []);
  const [index, setIndex] = useState<number>(restored.current?.index ?? 0);
  const [runId, setRunId] = useState<number | null>(restored.current?.runId ?? null);
  const [isPlaying, setIsPlaying] = useState(false);
  // True when the session intends to play (autoplay). Mirrors wantsPlayRef so an external
  // player component can read it to decide whether to autoplay when it mounts.
  const [wantsPlay, setWantsPlayState] = useState(false);
  const [currentTime, setCurrentTime] = useState(restored.current?.currentTime ?? 0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState<number>(loadVolume());
  const [muted, setMuted] = useState(false);
  // Relative loudness (0..1, estimate — see schema-proposal.md), for the meter/warnings.
  const [level, setLevel] = useState(0);
  const [sustainedLevel, setSustainedLevel] = useState(0);

  // Refs mirror state so the once-bound audio listeners never read stale values.
  const queueRef = useRef(queue);
  const indexRef = useRef(index);
  const runIdRef = useRef(runId);
  const wantsPlayRef = useRef(false);
  const pendingSeekRef = useRef<number>(restored.current?.currentTime ?? 0);
  const startedKeyRef = useRef<string | null>(null);
  const clipStartRef = useRef<number | null>(null);
  const clipEndRef = useRef<number | null>(null);
  const finishingRef = useRef(false);
  // Web Audio metering state.
  const meterRef = useRef<{
    ctx: AudioContext;
    analyser: AnalyserNode;
    data: Float32Array<ArrayBuffer>;
  } | null>(null);
  const meterFailedRef = useRef(false);
  const avgSumRef = useRef(0);
  const avgCountRef = useRef(0);
  const peakRef = useRef(0);
  const sustainedRef = useRef(0);
  const gainRef = useRef(1);
  // Latest external-item predicate + imperative controls + play state, read from
  // once-bound listeners without re-binding them.
  const isExternalRef = useRef(isExternalItem);
  const externalControlsRef = useRef<ExternalControls | null>(null);
  const isPlayingRef = useRef(isPlaying);
  queueRef.current = queue;
  indexRef.current = index;
  runIdRef.current = runId;
  isExternalRef.current = isExternalItem;
  isPlayingRef.current = isPlaying;
  gainRef.current = muted ? 0 : volume;

  // Keep the wantsPlay ref and its mirror-state in lockstep.
  const setWants = useCallback((value: boolean) => {
    wantsPlayRef.current = value;
    setWantsPlayState(value);
  }, []);

  const isExternal = useCallback(
    (item: QueueItem | null | undefined): boolean => Boolean(item && isExternalRef.current?.(item)),
    []
  );

  const currentItem = queue[index] ?? null;
  const currentUrl = currentItem?.media_url ?? null;
  const currentKey = currentItem ? itemKey(currentItem) : null;
  clipStartRef.current = currentItem?.track.clip_start_seconds ?? null;
  clipEndRef.current = currentItem?.track.clip_end_seconds ?? null;

  const recordEvent = useCallback(
    (type: PlaybackEventType, item: QueueItem | null, progress?: number, dur?: number) => {
      if (!item) {
        return;
      }
      const avg = avgCountRef.current > 0 ? avgSumRef.current / avgCountRef.current : null;
      void api
        .recordPlaybackEvent({
          event_type: type,
          track_id: item.track.id,
          media_asset_id: item.media_asset_id ?? null,
          playlist_run_id: runIdRef.current || null,
          queue_position: item.position,
          progress_seconds: Number.isFinite(progress) ? progress ?? null : null,
          duration_seconds: Number.isFinite(dur) ? dur ?? null : null,
          avg_level: avg,
          peak_level: peakRef.current > 0 ? peakRef.current : null,
          output_gain: gainRef.current
        })
        .catch(() => {
          /* history is best-effort; never block playback on it */
        });
    },
    []
  );

  // Lazily build the Web Audio graph on the first user-gesture play. A
  // MediaElementSource taps the element's audio; failure leaves playback untouched.
  const ensureMeter = useCallback(() => {
    if (meterRef.current || meterFailedRef.current) {
      return;
    }
    const element = audioRef.current;
    if (!element) {
      return;
    }
    try {
      const Ctor: typeof AudioContext =
        window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctor();
      const source = ctx.createMediaElementSource(element);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(ctx.destination);
      source.connect(analyser);
      meterRef.current = { ctx, analyser, data: new Float32Array(analyser.fftSize) };
    } catch {
      meterFailedRef.current = true;
    }
  }, []);

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
          setWants(false);
          audio?.pause();
          externalControlsRef.current?.pause();
        }
        return;
      }
      if (opts.recordSkip) {
        const leaving = items[indexRef.current];
        if (isExternal(leaving)) {
          // No accurate progress from the embed; omit it rather than log a false early-skip.
          recordEvent("skipped", leaving);
        } else if (audio) {
          recordEvent("skipped", leaving, audio.currentTime, audio.duration);
        }
      }
      pendingSeekRef.current = 0;
      setWants(opts.play ?? wantsPlayRef.current);
      setIndex(target);
    },
    [recordEvent, setWants, isExternal]
  );

  // Bind audio element listeners exactly once.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.volume = volume;

    const finishTrack = () => {
      if (finishingRef.current) {
        return;
      }
      finishingRef.current = true;
      const item = queueRef.current[indexRef.current] ?? null;
      recordEvent("completed", item, audio.currentTime, audio.duration);
      startedKeyRef.current = null;
      setWants(true);
      goToIndex(indexRef.current + 1, { play: true });
    };

    const onTime = () => {
      setCurrentTime(audio.currentTime);
      // Honor a trim-out point: treat reaching clip_end like the track ending.
      const clipEnd = clipEndRef.current;
      if (clipEnd != null && audio.currentTime >= clipEnd) {
        finishTrack();
      }
    };
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
    const onEnded = () => finishTrack();

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
    // External providers (e.g. a YouTube embed) play through their own official player, not
    // this element. Park and silence it so a previous local track stops, and hand control to
    // the embed component, which drives playback and calls externalEnded to advance.
    if (isExternal(currentItem)) {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      setCurrentTime(0);
      setDuration(0);
      finishingRef.current = false;
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
        // An external (e.g. YouTube) item also has no media_url but IS playable, so stop on it.
        while (next < items.length && !items[next]?.media_url && !isExternal(items[next])) {
          next += 1;
        }
        if (next < items.length) {
          startedKeyRef.current = null;
          setIndex(next);
          return;
        }
        setWants(false);
      }
      setIsPlaying(false);
      return;
    }
    finishingRef.current = false;
    // Reset per-track loudness accumulators.
    avgSumRef.current = 0;
    avgCountRef.current = 0;
    peakRef.current = 0;
    audio.src = currentUrl;
    audio.load();
    // Resume a restored mid-track position if there is one, otherwise honor the
    // track's trim-in point so YouTube intros are skipped.
    const seekTo = pendingSeekRef.current > 0 ? pendingSeekRef.current : clipStartRef.current ?? 0;
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

  // Loudness metering loop. Reads the analyser each frame, accumulates a per-track
  // average + peak, and maintains a slow EWMA used for sustained-loudness warnings.
  useEffect(() => {
    let raf = 0;
    let frame = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const meter = meterRef.current;
      const element = audioRef.current;
      if (!meter || !element || element.paused) {
        return;
      }
      meter.analyser.getFloatTimeDomainData(meter.data);
      let sumSquares = 0;
      let peak = 0;
      for (let i = 0; i < meter.data.length; i += 1) {
        const sample = meter.data[i];
        sumSquares += sample * sample;
        const amp = Math.abs(sample);
        if (amp > peak) {
          peak = amp;
        }
      }
      const rms = Math.sqrt(sumSquares / meter.data.length);
      // Map RMS to a perceptual-ish 0..1 "loudness" estimate (music RMS is well
      // below full scale). This is relative, not calibrated SPL.
      const loud = Math.min(1, rms * 3.2);
      avgSumRef.current += loud;
      avgCountRef.current += 1;
      if (peak > peakRef.current) {
        peakRef.current = peak;
      }
      // Fast-ish EWMA so sustained-loudness warnings err toward firing early.
      sustainedRef.current = sustainedRef.current * 0.98 + loud * 0.02;
      frame += 1;
      if (frame % 6 === 0) {
        setLevel(loud);
        setSustainedLevel(sustainedRef.current);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // --- Controls -------------------------------------------------------------
  // Build/resume the audio graph; must run inside a user gesture (play/generate).
  const startMeter = useCallback(() => {
    ensureMeter();
    void meterRef.current?.ctx.resume?.();
  }, [ensureMeter]);

  const loadQueue = useCallback(
    (run: QueueRun, opts: { autoplay?: boolean } = {}) => {
      startMeter();
      pendingSeekRef.current = 0;
      startedKeyRef.current = null;
      setWants(opts.autoplay ?? true);
      setQueue(run.items);
      setRunId(run.id || null);
      setIndex(0);
    },
    [startMeter, setWants]
  );

  const playAt = useCallback(
    (target: number) => {
      startMeter();
      const sameTrack = target === indexRef.current;
      setWants(true);
      if (sameTrack) {
        if (isExternal(queueRef.current[target])) {
          externalControlsRef.current?.play();
        } else {
          void audioRef.current?.play().catch(() => setIsPlaying(false));
        }
        return;
      }
      goToIndex(target, { recordSkip: true, play: true });
    },
    [goToIndex, startMeter, setWants, isExternal]
  );

  const togglePlay = useCallback(() => {
    const current = queueRef.current[indexRef.current] ?? null;
    // External (e.g. YouTube) tracks play in their own iframe; drive it through the controls
    // it registered rather than our <video> element.
    if (isExternal(current)) {
      if (isPlayingRef.current) {
        setWants(false);
        externalControlsRef.current?.pause();
      } else {
        setWants(true);
        externalControlsRef.current?.play();
      }
      return;
    }
    const audio = audioRef.current;
    if (!audio || !currentUrl) {
      return;
    }
    if (audio.paused) {
      startMeter();
      setWants(true);
      void audio.play().catch(() => setIsPlaying(false));
    } else {
      setWants(false);
      audio.pause();
    }
  }, [currentUrl, startMeter, setWants, isExternal]);

  const pause = useCallback(() => {
    setWants(false);
    if (isExternal(queueRef.current[indexRef.current])) {
      externalControlsRef.current?.pause();
      return;
    }
    audioRef.current?.pause();
  }, [setWants, isExternal]);

  // --- External (YouTube) player bridge -------------------------------------
  // The embed component registers imperative controls on ready, reports play/pause so the
  // transport bar stays in sync, and calls externalEnded so the queue advances at end of video.
  const registerExternalControls = useCallback((controls: ExternalControls | null) => {
    externalControlsRef.current = controls;
  }, []);

  const notifyExternalState = useCallback(
    (playing: boolean, progress?: number, dur?: number) => {
      setIsPlaying(playing);
      const item = queueRef.current[indexRef.current] ?? null;
      if (!item) {
        return;
      }
      const key = itemKey(item);
      if (playing && key !== startedKeyRef.current) {
        startedKeyRef.current = key;
        recordEvent("started", item, progress, dur);
      }
    },
    [recordEvent]
  );

  const externalEnded = useCallback(
    (progress?: number, dur?: number) => {
      if (finishingRef.current) {
        return;
      }
      finishingRef.current = true;
      const item = queueRef.current[indexRef.current] ?? null;
      recordEvent("completed", item, progress, dur);
      startedKeyRef.current = null;
      setWants(true);
      goToIndex(indexRef.current + 1, { play: true });
    },
    [recordEvent, goToIndex, setWants]
  );

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

  // Insert items immediately after the current track (used to stage an A/B cover comparison).
  const spliceNext = useCallback((items: QueueItem[]) => {
    if (items.length === 0) {
      return;
    }
    setQueue((current) => {
      const at = Math.min(indexRef.current + 1, current.length);
      return [...current.slice(0, at), ...items, ...current.slice(at)];
    });
  }, []);

  const clear = useCallback(() => {
    setWants(false);
    startedKeyRef.current = null;
    audioRef.current?.pause();
    externalControlsRef.current?.pause();
    setQueue([]);
    setIndex(0);
    setRunId(null);
    try {
      localStorage.removeItem(SESSION_KEY);
    } catch {
      /* ignore */
    }
  }, [setWants]);

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
      level,
      sustainedLevel,
      wantsPlay,
      loadQueue,
      playAt,
      togglePlay,
      pause,
      next,
      previous,
      seek,
      setVolume,
      toggleMute,
      removeAt,
      moveItem,
      spliceNext,
      clear,
      registerExternalControls,
      notifyExternalState,
      externalEnded
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
      level,
      sustainedLevel,
      wantsPlay,
      loadQueue,
      playAt,
      togglePlay,
      pause,
      next,
      previous,
      seek,
      setVolume,
      toggleMute,
      removeAt,
      moveItem,
      spliceNext,
      clear,
      registerExternalControls,
      notifyExternalState,
      externalEnded
    ]
  );
}

export type PlayerApi = ReturnType<typeof usePlayer>;

function itemKey(item: QueueItem): string {
  return `${item.position}:${item.track.id}`;
}
