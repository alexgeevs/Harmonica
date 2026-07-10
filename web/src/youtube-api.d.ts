// Minimal typings for the parts of YouTube's official IFrame Player API we use.
// The script is loaded lazily and only after the user consents (see youtube.ts); these
// declarations just describe the global it installs. Full API:
// https://developers.google.com/youtube/iframe_api_reference
export {};

declare global {
  interface YTPlayer {
    playVideo(): void;
    pauseVideo(): void;
    loadVideoById(options: { videoId: string; startSeconds?: number }): void;
    cueVideoById(options: { videoId: string; startSeconds?: number }): void;
    getCurrentTime(): number;
    getDuration(): number;
    destroy(): void;
  }

  interface YTPlayerEvent {
    target: YTPlayer;
    data: number;
  }

  interface YTPlayerOptions {
    videoId: string;
    playerVars?: Record<string, string | number | undefined>;
    events?: {
      onReady?: (event: YTPlayerEvent) => void;
      onStateChange?: (event: YTPlayerEvent) => void;
      onError?: (event: YTPlayerEvent) => void;
    };
  }

  interface YTNamespace {
    Player: new (element: HTMLElement | string, options: YTPlayerOptions) => YTPlayer;
    PlayerState: {
      ENDED: number;
      PLAYING: number;
      PAUSED: number;
      BUFFERING: number;
      CUED: number;
      UNSTARTED: number;
    };
  }

  interface Window {
    YT?: YTNamespace;
    onYouTubeIframeAPIReady?: () => void;
  }
}
