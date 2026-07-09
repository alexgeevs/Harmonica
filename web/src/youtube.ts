import type { Track } from "./types";

// Reported by GET /youtube/config. `enabled` mirrors the youtube_embed_enabled setting;
// `has_api_key` is only whether an OPTIONAL Data API key is present (never the key itself).
export type YouTubeConfig = {
  enabled: boolean;
  has_api_key: boolean;
  providers: string[];
};

// A third-party embed attached to a track (currently only YouTube). Mirrors the backend
// EmbedRead schema. `external_id` is the video id; `start_seconds` is the official start offset.
export type TrackEmbed = {
  id: number;
  provider: string;
  external_id: string;
  url?: string | null;
  start_seconds?: number | null;
};

const CONSENT_KEY = "harmonica.youtube.consent.v1";

// Whether the user has agreed to load YouTube's player. We keep this separate from the
// youtube_embed_enabled setting: enabling the feature says "I want YouTube songs to play",
// consent says "I accept that YouTube's player loads and sets its own cookies". We never
// request anything from youtube.com until consent is granted.
export function hasYouTubeConsent(): boolean {
  try {
    return localStorage.getItem(CONSENT_KEY) === "granted";
  } catch {
    return false;
  }
}

export function setYouTubeConsent(granted: boolean): void {
  try {
    if (granted) {
      localStorage.setItem(CONSENT_KEY, "granted");
    } else {
      localStorage.removeItem(CONSENT_KEY);
    }
  } catch {
    /* storage unavailable (private mode); consent stays in memory for this session */
  }
}

/** The YouTube embed for a track, if it has one. */
export function youtubeEmbedFor(track: Track | null | undefined): TrackEmbed | null {
  if (!track?.embeds) {
    return null;
  }
  return track.embeds.find((embed) => embed.provider === "youtube") ?? null;
}

// The official IFrame Player API. Requesting this from youtube.com is exactly what sets
// YouTube's cookies, so it is loaded lazily and ONLY after the consent gate is accepted.
const API_SRC = "https://www.youtube.com/iframe_api";
let apiPromise: Promise<YTNamespace> | null = null;

export function loadYouTubeApi(): Promise<YTNamespace> {
  if (apiPromise) {
    return apiPromise;
  }
  apiPromise = new Promise<YTNamespace>((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("YouTube API needs a browser"));
      return;
    }
    if (window.YT?.Player) {
      resolve(window.YT);
      return;
    }
    // The API calls this global once the script finishes loading. Chain any prior handler
    // so we don't clobber a second consumer.
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      if (window.YT?.Player) {
        resolve(window.YT);
      } else {
        reject(new Error("YouTube API loaded without a Player"));
      }
    };
    if (!document.querySelector(`script[src="${API_SRC}"]`)) {
      const script = document.createElement("script");
      script.src = API_SRC;
      script.async = true;
      script.onerror = () => reject(new Error("Could not load the YouTube player"));
      document.head.appendChild(script);
    }
  });
  return apiPromise;
}
