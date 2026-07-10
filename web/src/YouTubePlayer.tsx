import { useEffect, useRef } from "react";
import { Youtube } from "lucide-react";
import { loadYouTubeApi } from "./youtube";
import type { PlayerApi } from "./usePlayer";

/**
 * Plays a track that has a YouTube embed through YouTube's OFFICIAL IFrame player.
 *
 * This is deliberately the plain, compliant embed: the video is visible, YouTube's own
 * controls and branding are shown, and ads (if any) play as YouTube serves them. Harmonica
 * never downloads the video, hides it to play audio-only, strips ads, or extracts the audio
 * track — all of those are prohibited by YouTube's terms. We only tell the official player
 * which video to show and where to start.
 *
 * The player is created only when this component mounts, which only happens after the user
 * has enabled YouTube playback AND accepted the consent gate, so no request reaches YouTube
 * before then. It reports back to the shared player hook so the queue advances when a video
 * ends and the transport bar reflects play/pause.
 */
export function YouTubePlayer(props: {
  player: PlayerApi;
  videoId: string;
  startSeconds: number | null;
}) {
  const { player, videoId, startSeconds } = props;
  const hostRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const readyRef = useRef(false);
  // Autoplay only if the session was already playing when we reached this track.
  const autoplayRef = useRef(player.wantsPlay);
  autoplayRef.current = player.wantsPlay;
  // Latest requested video, so onReady can catch up if the queue advanced while the
  // player was still loading.
  const wantedRef = useRef({ videoId, startSeconds });
  wantedRef.current = { videoId, startSeconds };

  useEffect(() => {
    let cancelled = false;
    const initial = wantedRef.current;
    loadYouTubeApi()
      .then((YT) => {
        const host = hostRef.current;
        if (cancelled || !host) {
          return;
        }
        // YT replaces this node with its <iframe>, so give it a throwaway child.
        const target = document.createElement("div");
        host.appendChild(target);
        const autoplay = autoplayRef.current;
        const instance = new YT.Player(target, {
          videoId: initial.videoId,
          playerVars: {
            autoplay: autoplay ? 1 : 0,
            start: toStart(initial.startSeconds),
            playsinline: 1,
            rel: 0,
            origin: window.location.origin
          },
          events: {
            onReady: (event) => {
              readyRef.current = true;
              player.registerExternalControls({
                play: () => event.target.playVideo(),
                pause: () => event.target.pauseVideo()
              });
              const wanted = wantedRef.current;
              if (wanted.videoId !== initial.videoId) {
                // The queue moved on while the player was loading; catch up.
                showVideo(event.target, wanted.videoId, wanted.startSeconds, autoplayRef.current);
              } else if (autoplayRef.current) {
                event.target.playVideo();
              }
            },
            onStateChange: (event) => {
              const current = () => safeNumber(() => event.target.getCurrentTime());
              const total = () => safeNumber(() => event.target.getDuration());
              if (event.data === YT.PlayerState.ENDED) {
                player.externalEnded(current(), total());
              } else if (event.data === YT.PlayerState.PLAYING) {
                player.notifyExternalState(true, current(), total());
              } else if (event.data === YT.PlayerState.PAUSED) {
                player.notifyExternalState(false, current(), total());
              }
            }
          }
        });
        playerRef.current = instance;
      })
      .catch(() => {
        /* API failed to load; the now-stage just shows an empty frame. Non-fatal. */
      });

    return () => {
      cancelled = true;
      readyRef.current = false;
      player.registerExternalControls(null);
      try {
        playerRef.current?.destroy();
      } catch {
        /* already gone */
      }
      playerRef.current = null;
    };
    // Created ONCE per mount. Reusing one iframe across queue advances is what keeps the
    // browser from exiting fullscreen between songs: removing the iframe would force it out.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Swap videos inside the SAME player when the queue advances. The iframe survives, so
  // fullscreen (and the loaded player) persist from one song to the next.
  useEffect(() => {
    const instance = playerRef.current;
    if (!instance || !readyRef.current) {
      return; // still loading; onReady catches up from wantedRef
    }
    showVideo(instance, videoId, startSeconds, autoplayRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  return <div className="youtube-stage" ref={hostRef} />;
}

function toStart(startSeconds: number | null): number | undefined {
  return startSeconds != null ? Math.max(0, Math.floor(startSeconds)) : undefined;
}

// loadVideoById plays immediately; cueVideoById shows the video and waits for the user.
function showVideo(
  instance: YTPlayer,
  videoId: string,
  startSeconds: number | null,
  play: boolean
): void {
  try {
    const options = { videoId, startSeconds: toStart(startSeconds) };
    if (play) {
      instance.loadVideoById(options);
    } else {
      instance.cueVideoById(options);
    }
  } catch {
    /* player torn down mid-change; the next mount recovers */
  }
}

/**
 * Shown in place of the player until the user accepts loading YouTube. Requesting YouTube's
 * script is what sets YouTube's cookies, so we ask first — consistent with keeping Harmonica
 * itself cookie-light.
 */
export function YouTubeConsentGate(props: { onAccept: () => void }) {
  return (
    <div className="youtube-gate">
      <div className="youtube-gate-icon">
        <Youtube size={30} />
      </div>
      <h4>Play this song on YouTube?</h4>
      <p>
        This song plays through YouTube's official player. Loading it contacts YouTube, which
        sets its own cookies and may show ads. Harmonica does not remove either. Nothing is
        requested from YouTube until you accept.
      </p>
      <button className="primary" onClick={props.onAccept}>
        Load the YouTube player
      </button>
      <small>You can turn YouTube playback off again in Settings.</small>
    </div>
  );
}

function safeNumber(read: () => number): number | undefined {
  try {
    const value = read();
    return Number.isFinite(value) ? value : undefined;
  } catch {
    return undefined;
  }
}
