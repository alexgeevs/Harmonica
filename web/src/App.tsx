import {
  BarChart3,
  Check,
  ClipboardCheck,
  Clock,
  Download,
  GitMerge,
  Library as LibraryIcon,
  ListMusic,
  LogOut,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Settings as SettingsIcon,
  SkipBack,
  SkipForward,
  Smartphone,
  Sparkles,
  Star,
  Trash2,
  Upload,
  Video,
  Volume2,
  VolumeX,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import { api, configsSupported, savedQueuesSupported } from "./api";
import {
  applyTheme,
  BAR_OPTIONS,
  DARK_TONES,
  loadTheme,
  matchThemePreset,
  saveTheme,
  SURFACE_OPTIONS,
  THEME_PRESETS,
  themePresetPreview,
  type ThemeSelection
} from "./theme";
import { displayArtist, formatTime, pct, whyMath, whyReasons } from "./format";
import CurateView from "./CurateView";
import { matchPreset, PRESETS, type Preset } from "./presets";
import { usePlayer, type PlayerApi } from "./usePlayer";
import { comparisonMeta, useCoverComparison } from "./useCoverComparison";
import { YouTubeConsentGate, YouTubePlayer } from "./YouTubePlayer";
import {
  hasYouTubeConsent,
  setYouTubeConsent,
  youtubeEmbedFor,
  type TrackEmbed,
  type YouTubeConfig
} from "./youtube";
import type {
  AppSettings,
  CoverSetRead,
  DeviceConfigDetail,
  Embed,
  ExportScope,
  ImportSummary,
  PlaybackEvent,
  QueueItem,
  RatingFactor,
  RunSummary,
  SettingControl,
  StatsSummary,
  Tag,
  Track,
  TrackGroup,
  WhyReason
} from "./types";

const ACTIVE_CONFIG_KEY = "harmonica.activeConfig";

function loadStoredConfig(): DeviceConfigDetail | null {
  try {
    const raw = localStorage.getItem(ACTIVE_CONFIG_KEY);
    return raw ? (JSON.parse(raw) as DeviceConfigDetail) : null;
  } catch {
    return null;
  }
}

type View = "queue" | "library" | "curate" | "stats" | "settings";

// Registered by SettingsView so the app shell can ask about unapplied changes before
// navigating away from Settings.
type SettingsGuard = {
  dirty: boolean;
  apply: () => Promise<void>;
  discard: () => void;
};

const VIEW_TITLES: Record<View, string> = {
  queue: "Listen",
  library: "Library",
  curate: "Curate",
  stats: "Insights",
  settings: "Settings"
};

export default function App() {
  // Whether YouTube playback is enabled, read by the player's external-item predicate. Kept in
  // a ref so the predicate stays stable; an effect below mirrors the setting into it.
  const embedStateRef = useRef({ enabled: false });
  const player = usePlayer(
    (item) => embedStateRef.current.enabled && Boolean(youtubeEmbedFor(item.track))
  );
  const [view, setView] = useState<View>("queue");
  // Leaving Settings with unapplied changes goes through a confirmation instead of silently
  // dropping the draft; SettingsView registers its state here while mounted.
  const settingsGuardRef = useRef<SettingsGuard | null>(null);
  const [pendingView, setPendingView] = useState<View | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [ratingFactors, setRatingFactors] = useState<RatingFactor[]>([]);
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [events, setEvents] = useState<PlaybackEvent[]>([]);
  const [savedRuns, setSavedRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Optional YouTube playback. `youtubeCfg` comes from the backend; `ytConsent` is the user's
  // acceptance of loading YouTube's player. Both default off, and nothing contacts YouTube
  // until the feature is enabled and consent is granted.
  const [youtubeCfg, setYoutubeCfg] = useState<YouTubeConfig | null>(null);
  const [ytConsent, setYtConsent] = useState<boolean>(hasYouTubeConsent());

  // Device profiles are entirely optional. null = local mode (full library,
  // global settings) — the default, identical to single-device use.
  const [activeConfig, setActiveConfig] = useState<DeviceConfigDetail | null>(loadStoredConfig);
  const [configsOk, setConfigsOk] = useState(false);

  // With a profile active, every request carries its identity header, so `tracks` (from
  // GET /tracks) is already exactly this profile's private library — empty for a brand-new
  // profile until it imports/scans. No client-side filtering needed.
  const libraryTracks = tracks;

  useEffect(() => {
    try {
      if (activeConfig) {
        localStorage.setItem(ACTIVE_CONFIG_KEY, JSON.stringify(activeConfig));
      } else {
        localStorage.removeItem(ACTIVE_CONFIG_KEY);
      }
    } catch {
      /* localStorage may be unavailable (private mode); profile stays in memory. */
    }
  }, [activeConfig]);

  // Cover A/B comparison (Phase E): inert unless two-level covers are on and a set is eligible.
  useCoverComparison(player, tracks, Boolean(settings?.cover_two_level_enabled));

  const videoStageRef = useRef<HTMLDivElement>(null);
  const videoParkRef = useRef<HTMLDivElement>(null);
  const embedsEnabled = Boolean(settings?.youtube_embed_enabled);
  // A YouTube embed on the current track takes over the now-stage (when the feature is on),
  // in place of any local video asset.
  const currentEmbed = embedsEnabled ? youtubeEmbedFor(player.currentItem?.track) : null;
  const currentIsVideo =
    !currentEmbed &&
    !player.currentItem?.track.audio_only &&
    selectedAsset(player.currentItem)?.asset_type === "video";

  useEffect(() => {
    embedStateRef.current.enabled = embedsEnabled;
  }, [embedsEnabled]);

  // Hearing health: is the playing asset compressed (lossy)? Warnings are stricter for it.
  const currentCompressed = selectedAsset(player.currentItem)?.is_lossless === false;
  const loudnessThreshold = (settings?.loudness_warning_level ?? 0.7) - (currentCompressed ? 0.1 : 0);
  const loudnessWarn =
    Boolean(settings?.loudness_warning_enabled) && player.isPlaying && player.sustainedLevel > loudnessThreshold;

  const compressedRunRef = useRef(0);
  const [showBreak, setShowBreak] = useState(false);
  useEffect(() => {
    if (!player.currentKey) {
      return;
    }
    if (currentCompressed) {
      compressedRunRef.current += 1;
      // Conservative: after just two compressed songs in a row, stop and prompt a break.
      if (settings?.compressed_break_reminder && compressedRunRef.current >= 2) {
        setShowBreak(true);
        player.pause();
      }
    } else {
      compressedRunRef.current = 0;
      setShowBreak(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player.currentKey]);

  useEffect(() => {
    void refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the single <video> element mounted while moving it between the now-playing
  // stage (when watching a visual track on the Listen view) and a hidden park (so
  // audio keeps playing everywhere else). appendChild moves it without reloading.
  useEffect(() => {
    const element = player.mediaEl;
    if (!element) {
      return;
    }
    const onStage = view === "queue" && currentIsVideo && videoStageRef.current;
    const target = onStage ? videoStageRef.current : videoParkRef.current;
    if (target && element.parentElement !== target) {
      target.appendChild(element);
    }
  }, [view, currentIsVideo, player.mediaEl, player.currentKey]);

  // Keyboard transport — the hallmark of a real player. Ignored while typing.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) {
        return;
      }
      if (showBreak) {
        return; // playback is paused for a break; ignore transport keys
      }
      if (event.code === "Space") {
        event.preventDefault();
        player.togglePlay();
      } else if (event.code === "ArrowRight" && event.shiftKey) {
        player.next();
      } else if (event.code === "ArrowLeft" && event.shiftKey) {
        player.previous();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [player, showBreak]);

  async function refreshAll() {
    setError(null);
    try {
      const [nextSettings, nextFactors, nextTracks, nextStats] = await Promise.all([
        api.settings(),
        api.ratingFactors(),
        api.tracks(),
        api.stats()
      ]);
      setSettings(nextSettings);
      setRatingFactors(nextFactors);
      setTracks(nextTracks);
      setStats(nextStats);
      void api.playbackEvents(300).then(setEvents).catch(() => undefined);
      void refreshSavedRuns();
      void configsSupported().then(setConfigsOk).catch(() => setConfigsOk(false));
      void api.listTags().then(setTags).catch(() => setTags([]));
      // Best-effort: an older backend without the endpoint just leaves YouTube off.
      void api.youtubeConfig().then(setYoutubeCfg).catch(() => setYoutubeCfg(null));
    } catch (err) {
      setError(message(err, "Could not reach the Harmonica backend. It may not be running."));
    }
  }

  async function refreshSavedRuns() {
    if (!(await savedQueuesSupported())) {
      setSavedRuns(null);
      return;
    }
    try {
      setSavedRuns(await api.listRuns(40));
    } catch {
      setSavedRuns(null);
    }
  }

  async function refreshStats() {
    void api.stats().then(setStats).catch(() => undefined);
    void api.playbackEvents(300).then(setEvents).catch(() => undefined);
  }

  function refreshTags() {
    void api.listTags().then(setTags).catch(() => undefined);
  }

  async function generateQueue(length: number, seed: string, queueTags: string[]) {
    setBusy(true);
    setError(null);
    try {
      const run = await api.generateQueue(
        length,
        seed.trim() || undefined,
        activeConfig?.id ?? null,
        queueTags
      );
      player.loadQueue(run, { autoplay: true });
      void refreshSavedRuns();
    } catch (err) {
      setError(message(err, "Could not generate a queue"));
    } finally {
      setBusy(false);
    }
  }

  async function claimConfig(name: string, passphrase: string) {
    // Throws on bad passphrase / unknown name; the panel surfaces the message.
    const detail = await api.claimConfig(name, passphrase);
    setActiveConfig(detail);
    return detail;
  }

  async function createConfig(name: string, passphrase: string, trackIds: number[]) {
    // New profiles copy the current global settings as their snapshot.
    const snapshot = settings ? settingsToDraft(settings) : {};
    const detail = await api.createConfig({
      name,
      passphrase,
      settings: snapshot,
      track_ids: trackIds
    });
    setActiveConfig(detail);
    return detail;
  }

  function switchToLocal() {
    setActiveConfig(null);
  }

  function grantYouTubeConsent() {
    // Only now may YouTube's player be loaded. Persisted so the gate isn't shown every time.
    setYouTubeConsent(true);
    setYtConsent(true);
  }

  async function loadSavedRun(id: number) {
    setBusy(true);
    try {
      const run = await api.getRun(id);
      player.loadQueue(run, { autoplay: false });
      setView("queue");
    } catch (err) {
      setError(message(err, "Could not load that queue"));
    } finally {
      setBusy(false);
    }
  }

  async function renameRun(id: number, name: string) {
    try {
      await api.renameRun(id, name);
      void refreshSavedRuns();
    } catch (err) {
      setError(message(err, "Could not rename that session"));
    }
  }

  async function deleteRun(id: number) {
    try {
      await api.deleteRun(id);
      void refreshSavedRuns();
    } catch (err) {
      setError(message(err, "Could not delete that session"));
    }
  }

  async function rateTrack(track: Track, factorKey: string, value: number | null) {
    const current = tracks.find((item) => item.id === track.id) ?? track;
    // Send ONLY the tapped factor — each rating action is one data point (the server treats a
    // quick re-tap as a correction of the last mark). The displayed rating is the average of all
    // past marks (recomputed server-side), so we must NOT resend the other factors' averages as
    // if they were fresh ratings.
    const optimistic = { ...current.ratings, [factorKey]: value };
    setTracks((cur) =>
      cur.map((item) => (item.id === track.id ? { ...item, ratings: optimistic } : item))
    );
    try {
      const saved = await api.updateTrackFields(track.id, { ratings: { [factorKey]: value } });
      setTracks((cur) => cur.map((item) => (item.id === saved.id ? saved : item)));
      void refreshStats();
    } catch (err) {
      setError(message(err, "Could not save the rating"));
    }
  }

  async function saveTrack(track: Track) {
    setBusy(true);
    setError(null);
    try {
      const saved = await api.updateTrack(track);
      setTracks((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      void refreshStats();
      refreshTags(); // a save may have created a new tag or moved counts
      return saved;
    } catch (err) {
      setError(message(err, "Could not save the track"));
      return track;
    } finally {
      setBusy(false);
    }
  }

  async function saveSettings(values: Record<string, number | boolean>) {
    setBusy(true);
    setError(null);
    try {
      setSettings(await api.updateSettings(values));
    } catch (err) {
      setError(message(err, "Could not save settings"));
    } finally {
      setBusy(false);
    }
  }

  function navigateTo(next: View) {
    if (view === "settings" && next !== "settings" && settingsGuardRef.current?.dirty) {
      setPendingView(next);
      return;
    }
    setView(next);
  }

  return (
    <div className="app-shell">
      <Sidebar view={view} onView={navigateTo} trackCount={tracks.length} />

      <main className="workspace">
        <header className="topbar">
          <h2>{VIEW_TITLES[view]}</h2>
          <div className="topbar-actions">
            {error ? <span className="error-text">{error}</span> : null}
            {!settings && !error ? <span className="connecting">Connecting…</span> : null}
            <button className="icon-button" title="Refresh" onClick={() => void refreshAll()}>
              <RefreshCw size={18} />
            </button>
          </div>
        </header>

        {activeConfig ? (
          <div className="health-banners">
            <div className="health-banner profile">
              <Smartphone size={16} />
              <span>
                Profile <strong>{activeConfig.name}</strong> is active · {tracks.length}{" "}
                {tracks.length === 1 ? "song" : "songs"} in your library.
                {tracks.length === 0
                  ? " Library empty. Import or scan songs to fill it. Anything the household already has is linked rather than copied."
                  : ""}
              </span>
              <button className="link-button" onClick={switchToLocal}>
                Switch to local
              </button>
            </div>
          </div>
        ) : null}

        {loudnessWarn && !showBreak ? (
          <div className="health-banners">
            <div className="health-banner warn">
              <Volume2 size={16} />
              <span>
                Sustained loudness looks high{currentCompressed ? " for compressed audio" : ""}. Consider
                turning it down to protect your hearing. <em>This is a relative estimate, not an exact
                measurement.</em>
              </span>
            </div>
          </div>
        ) : null}

        <div className="view-scroll">
          {view === "queue" ? (
            <QueueView
              player={player}
              busy={busy}
              defaultLength={settings?.default_playlist_length ?? 50}
              savedRuns={savedRuns}
              currentIsVideo={currentIsVideo}
              videoStageRef={videoStageRef}
              currentEmbed={currentEmbed}
              ytConsent={ytConsent}
              onGrantYouTubeConsent={grantYouTubeConsent}
              ratingFactors={ratingFactors}
              liveTracks={tracks}
              tags={tags}
              showMath={Boolean(settings?.why_show_math)}
              onRate={rateTrack}
              onGenerate={generateQueue}
              onLoadRun={loadSavedRun}
              onRefreshSaved={refreshSavedRuns}
              onRenameRun={renameRun}
              onDeleteRun={deleteRun}
            />
          ) : null}

          {view === "library" ? (
            <LibraryView
              tracks={libraryTracks}
              tags={tags}
              onTagsChanged={refreshTags}
              ratingFactors={ratingFactors}
              busy={busy}
              currentTrackId={player.currentItem?.track.id ?? null}
              currentTime={player.currentTime}
              youtubeEnabled={embedsEnabled}
              onSave={saveTrack}
              onRate={rateTrack}
              onRescan={refreshAll}
            />
          ) : null}

          {view === "curate" ? (
            <CurateView
              tracks={tracks}
              spotifyEnabled={Boolean(settings?.spotify_enabled)}
              youtubeEnabled={embedsEnabled}
              onApplied={refreshAll}
            />
          ) : null}

          {view === "stats" && stats ? <StatsView stats={stats} tracks={tracks} events={events} /> : null}

          {view === "settings" && settings ? (
            <SettingsView
              settings={settings}
              ratingFactors={ratingFactors}
              busy={busy}
              onSave={saveSettings}
              guardRef={settingsGuardRef}
              onOpenCurate={() => navigateTo("curate")}
              configsEnabled={configsOk}
              activeConfig={activeConfig}
              allTracks={tracks}
              onClaim={claimConfig}
              onCreate={createConfig}
              onSwitchLocal={switchToLocal}
              onImported={refreshAll}
            />
          ) : null}
        </div>
      </main>

      <PlayerBar player={player} />
      {/* The single <video> element lives here whenever it isn't on the now-playing stage. */}
      <div ref={videoParkRef} className="video-park" aria-hidden />

      {showBreak ? (
        <BreakModal
          onClose={() => {
            setShowBreak(false);
            compressedRunRef.current = 0;
          }}
        />
      ) : null}

      {pendingView ? (
        <SettingsLeaveModal
          busy={busy}
          onApply={async () => {
            await settingsGuardRef.current?.apply();
            setView(pendingView);
            setPendingView(null);
          }}
          onDiscard={() => {
            settingsGuardRef.current?.discard();
            setView(pendingView);
            setPendingView(null);
          }}
          onStay={() => setPendingView(null)}
        />
      ) : null}
    </div>
  );
}

function SettingsLeaveModal(props: {
  busy: boolean;
  onApply: () => void;
  onDiscard: () => void;
  onStay: () => void;
}) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="confirm-modal">
        <h3>Apply your changes?</h3>
        <p>You have changed settings but not applied them yet.</p>
        <div className="confirm-actions">
          <button className="primary" disabled={props.busy} onClick={props.onApply}>
            Apply and continue
          </button>
          <button className="primary ghost-primary" onClick={props.onDiscard}>
            Discard changes
          </button>
          <button className="link-button" onClick={props.onStay}>
            Keep editing
          </button>
        </div>
      </div>
    </div>
  );
}

function BreakModal(props: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="break-modal">
        <div className="break-icon">
          <Clock size={26} />
        </div>
        <h3>It is advised that you take a short break</h3>
        <p>
          Playback is paused: that was two heavily compressed and lossy tracks in a row.
          Over-compressed music appears to be genuinely more fatiguing. In one lab study it caused
          lasting ear damage in guinea pigs that the same energy of ordinary music did not.
        </p>
        <p>
          A break is good in combination with looking at a distant object for at least 20 seconds.
        </p>
        <p className="break-source">
          See:{" "}
          <a className="break-link" href="https://econ.st/4dtOesh" target="_blank" rel="noreferrer">
            The Economist
          </a>
        </p>
        <button className="primary" onClick={props.onClose}>
          Resume playback
        </button>
        <small>You can soften or turn this off in Settings → Hearing health.</small>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

function Sidebar(props: { view: View; onView: (view: View) => void; trackCount: number }) {
  const items: { key: View; label: string; icon: JSX.Element }[] = [
    { key: "queue", label: "Listen", icon: <ListMusic size={18} /> },
    { key: "library", label: "Library", icon: <LibraryIcon size={18} /> },
    // Curation is an occasional act, not a daily surface: once the library holds
    // songs, the Curate page is opened from Settings instead of the sidebar.
    ...(props.trackCount === 0
      ? [{ key: "curate" as View, label: "Curate", icon: <ClipboardCheck size={18} /> }]
      : []),
    { key: "stats", label: "Insights", icon: <BarChart3 size={18} /> },
    { key: "settings", label: "Settings", icon: <SettingsIcon size={18} /> }
  ];
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">H</div>
        <div>
          <h1>Harmonica</h1>
          <p>{props.trackCount} tracks</p>
        </div>
      </div>
      <nav className="nav-buttons">
        {items.map((item) => (
          <button
            key={item.key}
            className={props.view === item.key ? "active" : ""}
            onClick={() => props.onView(item.key)}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <Sparkles size={14} />
        <span>Your library, sequenced by expected utility maximisation as opposed to at random.</span>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Persistent player bar
// ---------------------------------------------------------------------------

function PlayerBar(props: { player: PlayerApi }) {
  const { player } = props;
  const item = player.currentItem;
  const track = item?.track ?? null;
  const hasVideo = track?.assets.some((asset) => asset.asset_type === "video") ?? false;
  // Progress is shown within the trim window so a clipped song reads 0 → full.
  const clipStart = track?.clip_start_seconds ?? 0;
  const windowEnd = track?.clip_end_seconds ?? player.duration;
  const windowDuration = Math.max(windowEnd - clipStart, 0);
  const elapsed = Math.max(player.currentTime - clipStart, 0);
  const progress = windowDuration > 0 ? Math.min(elapsed / windowDuration, 1) : 0;

  return (
    <footer className={`player-bar ${item ? "" : "empty"}`}>
      <div className="player-meta">
        <div className="player-art" style={artStyle(track?.id ?? 0)}>
          {hasVideo ? <Video size={18} /> : <ListMusic size={18} />}
        </div>
        <div className="player-titles">
          <strong title={track?.title}>{track?.title ?? "Nothing playing"}</strong>
          <span>{track ? displayArtist(track) : "Generate a queue to start listening"}</span>
        </div>
      </div>

      <div className="player-center">
        <div className="player-controls">
          <button className="icon-button ghost" title="Previous" onClick={player.previous} disabled={!item}>
            <SkipBack size={18} />
          </button>
          <button className="play-button" title={player.isPlaying ? "Pause" : "Play"} onClick={player.togglePlay} disabled={!item}>
            {player.isPlaying ? <Pause size={20} /> : <Play size={20} />}
          </button>
          <button className="icon-button ghost" title="Next" onClick={player.next} disabled={!item}>
            <SkipForward size={18} />
          </button>
        </div>
        <div className="scrubber">
          <span>{formatTime(elapsed)}</span>
          <Seekbar
            value={progress}
            onSeek={(ratio) => player.seek(clipStart + ratio * windowDuration)}
            disabled={!item}
          />
          <span>{formatTime(windowDuration)}</span>
        </div>
      </div>

      <div className="player-right">
        <div
          className="loudness-meter"
          title="Relative loudness (estimate, not calibrated dB)"
          data-hot={player.sustainedLevel > 0.75 ? "true" : "false"}
        >
          <div className="loudness-fill" style={{ width: `${Math.round(player.level * 100)}%` }} />
        </div>
        {player.runId ? (
          <a className="icon-button ghost" title="Export .m3u8" href={`/playlist-runs/${player.runId}/m3u8`}>
            <Download size={18} />
          </a>
        ) : null}
        <button className="icon-button ghost" title={player.muted ? "Unmute" : "Mute"} onClick={player.toggleMute} disabled={!item}>
          {player.muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
        </button>
        <Seekbar
          className="volume"
          value={player.muted ? 0 : player.volume}
          onSeek={(ratio) => player.setVolume(ratio)}
          disabled={!item}
        />
      </div>
    </footer>
  );
}

function Seekbar(props: {
  value: number;
  onSeek: (ratio: number) => void;
  disabled?: boolean;
  className?: string;
}) {
  const clamped = Math.min(Math.max(props.value, 0), 1);
  function handle(event: React.MouseEvent<HTMLDivElement>) {
    if (props.disabled) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    props.onSeek(Math.min(Math.max(ratio, 0), 1));
  }
  return (
    <div
      className={`seekbar ${props.className ?? ""} ${props.disabled ? "disabled" : ""}`}
      onClick={handle}
      role="slider"
      aria-valuenow={Math.round(clamped * 100)}
    >
      <div className="seekbar-track">
        <div className="seekbar-fill" style={{ width: `${clamped * 100}%` }}>
          <span className="seekbar-thumb" />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Queue view
// ---------------------------------------------------------------------------

function QueueView(props: {
  player: PlayerApi;
  busy: boolean;
  defaultLength: number;
  savedRuns: RunSummary[] | null;
  currentIsVideo: boolean;
  videoStageRef: React.RefObject<HTMLDivElement>;
  currentEmbed: TrackEmbed | null;
  ytConsent: boolean;
  onGrantYouTubeConsent: () => void;
  ratingFactors: RatingFactor[];
  liveTracks: Track[];
  tags: Tag[];
  showMath: boolean;
  onRate: (track: Track, factorKey: string, value: number | null) => void;
  onGenerate: (length: number, seed: string, tags: string[]) => void;
  onLoadRun: (id: number) => void;
  onRefreshSaved: () => void;
  onRenameRun: (id: number, name: string) => void;
  onDeleteRun: (id: number) => void;
}) {
  const { player } = props;
  const [length, setLength] = useState(props.defaultLength);
  const [seed, setSeed] = useState("");
  const [queueTags, setQueueTags] = useState<string[]>([]);
  const item = player.currentItem;
  // Prefer the live track (with the latest ratings) over the queue snapshot.
  const liveTrack = item ? props.liveTracks.find((t) => t.id === item.track.id) ?? item.track : null;

  useEffect(() => setLength(props.defaultLength), [props.defaultLength]);

  function nameCurrentSession() {
    if (!player.runId || props.savedRuns === null) {
      return;
    }
    const existing = props.savedRuns.find((run) => run.id === player.runId);
    const name = window.prompt("Name this session", existing?.name ?? "")?.trim();
    if (name) {
      props.onRenameRun(player.runId, name);
    }
  }

  return (
    <section className="queue-view">
      <div className="now-column">
        <div className={`now-card ${props.currentIsVideo || props.currentEmbed ? "has-video" : ""}`}>
          {props.currentEmbed ? (
            <div className="now-stage">
              {props.ytConsent ? (
                <YouTubePlayer
                  player={player}
                  videoId={props.currentEmbed.external_id}
                  startSeconds={props.currentEmbed.start_seconds ?? null}
                />
              ) : (
                <YouTubeConsentGate onAccept={props.onGrantYouTubeConsent} />
              )}
            </div>
          ) : props.currentIsVideo ? (
            <div className="now-stage" ref={props.videoStageRef} />
          ) : (
            <div className="now-art" style={artStyle(item?.track.id ?? 0)}>
              {item?.track.assets.some((asset) => asset.asset_type === "video") ? (
                <Video size={42} />
              ) : (
                <ListMusic size={42} />
              )}
            </div>
          )}
          <div className="now-info">
            <p className="now-eyebrow">
              {item ? `Now playing · ${player.index + 1} of ${player.queue.length}` : "Nothing queued"}
            </p>
            <h3>{item?.track.title ?? "Generate a queue"}</h3>
            <span>{item ? displayArtist(item.track) : "Harmonica will compile your next listening session."}</span>
            {item ? <ChipRow groups={item.track.groups} subGroup={item.track.sub_group} /> : null}
          </div>
        </div>

        {item && liveTrack ? (
          <RateCard
            track={liveTrack}
            factors={props.ratingFactors}
            onRate={(key, value) => props.onRate(liveTrack, key, value)}
          />
        ) : null}

        <ComparisonCard player={player} />

        {item ? <WhyThisSong item={item} showMath={props.showMath} /> : null}

        <div className="generate-card">
          <h4>Build a session</h4>
          {props.tags.some((tag) => tag.name !== "Ignored" && tag.track_count > 0) ? (
            <div className="queue-tag-picker">
              {props.tags
                .filter((tag) => tag.name !== "Ignored" && tag.track_count > 0)
                .map((tag) => {
                  const on = queueTags.includes(tag.name);
                  return (
                    <button
                      key={tag.id}
                      className={`chip toggle ${on ? "on" : ""}`}
                      onClick={() =>
                        setQueueTags((cur) =>
                          on ? cur.filter((name) => name !== tag.name) : [...cur, tag.name]
                        )
                      }
                    >
                      {tag.name} <b>{tag.track_count}</b>
                    </button>
                  );
                })}
            </div>
          ) : null}
          {queueTags.length ? (
            <small className="queue-tag-note">
              Only songs tagged {queueTags.join(" or ")} will be queued.
            </small>
          ) : null}
          <div className="generate-row">
            <label>
              Length
              <input
                type="number"
                min={1}
                max={1000}
                value={length}
                onChange={(event) => setLength(Number(event.target.value))}
              />
            </label>
            <label>
              Seed <span className="hint">optional</span>
              <input value={seed} placeholder="reproducible" onChange={(event) => setSeed(event.target.value)} />
            </label>
            <button
              className="primary"
              disabled={props.busy}
              onClick={() => props.onGenerate(length, seed, queueTags)}
            >
              <RefreshCw size={16} />
              Generate
            </button>
          </div>
          {player.runId && props.savedRuns !== null ? (
            <button className="link save-session" onClick={nameCurrentSession}>
              <Save size={14} /> Name this session
            </button>
          ) : null}
          <SavedRuns
            runs={props.savedRuns}
            currentRunId={player.runId}
            onLoad={props.onLoadRun}
            onRefresh={props.onRefreshSaved}
            onRename={props.onRenameRun}
            onDelete={props.onDeleteRun}
          />
        </div>
      </div>

      <QueuePanel player={player} />
    </section>
  );
}

function QueuePanel(props: { player: PlayerApi }) {
  const { player } = props;
  if (player.queue.length === 0) {
    return (
      <div className="queue-panel empty-queue">
        <ListMusic size={34} />
        <p>Your queue is empty</p>
        <small>Generate a session and it will appear here.</small>
      </div>
    );
  }
  return (
    <div className="queue-panel">
      <div className="queue-head">
        <h4>Up next</h4>
        <span>{player.queue.length - player.index - 1} remaining</span>
      </div>
      <ol className="queue-list">
        {player.queue.map((entry, i) => (
          <QueueRow
            key={`${entry.position}-${entry.track.id}`}
            item={entry}
            isCurrent={i === player.index}
            isPast={i < player.index}
            onPlay={() => player.playAt(i)}
            onRemove={() => player.removeAt(i)}
            onUp={i > 0 ? () => player.moveItem(i, i - 1) : undefined}
            onDown={i < player.queue.length - 1 ? () => player.moveItem(i, i + 1) : undefined}
            isPlaying={i === player.index && player.isPlaying}
          />
        ))}
      </ol>
    </div>
  );
}

function QueueRow(props: {
  item: QueueItem;
  isCurrent: boolean;
  isPast: boolean;
  isPlaying: boolean;
  onPlay: () => void;
  onRemove: () => void;
  onUp?: () => void;
  onDown?: () => void;
}) {
  const { item } = props;
  return (
    <li className={`queue-row ${props.isCurrent ? "current" : ""} ${props.isPast ? "past" : ""}`}>
      <button className="queue-play" onClick={props.onPlay} title="Play">
        <span className="queue-art" style={artStyle(item.track.id)}>
          {props.isCurrent && props.isPlaying ? <Pause size={14} /> : <Play size={14} />}
        </span>
        <span className="queue-text">
          <strong>{item.track.title}</strong>
          <small>{displayArtist(item.track) || "—"}</small>
        </span>
      </button>
      <div className="queue-tags">
        {!item.media_url ? (
          <span className="tag soon" title="Media not available">
            soon
          </span>
        ) : null}
        {item.track.assets.some((asset) => asset.asset_type === "video") ? (
          <span className="tag video" title="Has video">
            <Video size={12} />
          </span>
        ) : null}
        {item.track.sub_group ? <span className="tag variant" title={`Variant family: ${item.track.sub_group}`}>var</span> : null}
      </div>
      <div className="queue-actions">
        <button className="mini" title="Move up" onClick={props.onUp} disabled={!props.onUp}>
          ▲
        </button>
        <button className="mini" title="Move down" onClick={props.onDown} disabled={!props.onDown}>
          ▼
        </button>
        <button className="mini danger" title="Remove" onClick={props.onRemove}>
          <X size={13} />
        </button>
      </div>
    </li>
  );
}

function RateCard(props: {
  track: Track;
  factors: RatingFactor[];
  onRate: (key: string, value: number | null) => void;
}) {
  const applicable = props.factors.filter((factor) => isFactorApplicable(factor, props.track));
  if (applicable.length === 0) {
    return null;
  }
  return (
    <div className="rate-card">
      <h4>
        <Star size={15} /> Rate this song
      </h4>
      <div className="rate-grid">
        {applicable.map((factor) => (
          <StarRating
            key={factor.key}
            label={factor.label}
            value={props.track.ratings[factor.key] ?? null}
            onChange={(value) => props.onRate(factor.key, value)}
          />
        ))}
      </div>
    </div>
  );
}

// Shown while the SECOND rendition of an A/B pair is playing: ask which was better, with a quick
// replay of the first to compare. Reuses a throwaway <audio> for the replay so the main player (and
// its loudness meter) is never disturbed — the verdict feeds the Bradley-Terry ranking.
function ComparisonCard(props: { player: PlayerApi }) {
  const { player } = props;
  const previewRef = useRef<HTMLAudioElement | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [submitted, setSubmitted] = useState<string | null>(null);

  const item = player.currentItem;
  const meta = comparisonMeta(item);

  useEffect(() => {
    // Stop any replay when the comparison track changes or the card unmounts.
    return () => {
      previewRef.current?.pause();
      previewRef.current = null;
    };
  }, [player.currentKey]);

  if (!item || !meta || meta.role !== "b") {
    return null;
  }
  const aItem = player.queue.find((q) => {
    const m = comparisonMeta(q);
    return m?.role === "a" && m.set_id === meta.set_id && q.track.id === meta.peer_track_id;
  });
  const itemKey = `${item.position}:${item.track.id}`;
  const alreadyDone = submitted === itemKey;

  function stopPreview() {
    previewRef.current?.pause();
    setPreviewing(false);
  }

  function replayFirst() {
    if (!aItem?.media_url) {
      return;
    }
    player.pause();
    let audio = previewRef.current;
    if (!audio) {
      audio = new Audio();
      previewRef.current = audio;
      audio.addEventListener("ended", () => setPreviewing(false));
    }
    audio.src = aItem.media_url;
    const fraction = player.duration > 0 ? player.currentTime / player.duration : 0;
    const startAt = aItem.track.clip_start_seconds ?? 0;
    audio.currentTime = startAt;
    const applyFraction = () => {
      const dur = audio?.duration ?? 0;
      if (audio && fraction > 0 && dur > 0) {
        audio.currentTime = Math.min(Math.max(startAt, fraction * dur), dur - 0.5);
      }
      audio?.removeEventListener("loadedmetadata", applyFraction);
    };
    audio.addEventListener("loadedmetadata", applyFraction);
    void audio.play().catch(() => setPreviewing(false));
    setPreviewing(true);
  }

  function submit(winner: number | null) {
    stopPreview();
    setSubmitted(itemKey);
    void api
      .submitCoverVerdict({
        sub_group: meta!.set_id,
        track_a_id: meta!.peer_track_id,
        track_b_id: item!.track.id,
        winner_track_id: winner,
        pct_b: player.duration > 0 ? player.currentTime / player.duration : null
      })
      .catch(() => {
        /* best-effort; the raw verdict log tolerates a retry next time */
      });
  }

  if (alreadyDone) {
    return (
      <div className="compare-card done">
        <Sparkles size={15} /> Your preference has been recorded.
      </div>
    );
  }

  const firstTitle = aItem?.track.title ?? "the first version";
  return (
    <div className="compare-card">
      <h4>
        <ListMusic size={15} /> Which version is better?
      </h4>
      <p className="compare-sub">
        You're hearing a second take of <strong>{item.track.title}</strong>. Compare it with the one
        just before it.
      </p>
      <div className="compare-actions">
        <button className="compare-vote" onClick={() => submit(meta.peer_track_id)}>
          The first was better
        </button>
        <button className="compare-vote neutral" onClick={() => submit(null)}>
          About the same
        </button>
        <button className="compare-vote" onClick={() => submit(item.track.id)}>
          This one's better
        </button>
      </div>
      <button className="compare-replay" onClick={previewing ? stopPreview : replayFirst}>
        {previewing ? "Stop and return to this version" : `▸ Replay ${firstTitle} to compare`}
      </button>
    </div>
  );
}

function WhyThisSong(props: { item: QueueItem; showMath: boolean }) {
  const reasons = whyReasons(props.item);
  const math = props.showMath ? whyMath(props.item) : null;
  return (
    <div className="why-card">
      <h4>
        <Sparkles size={15} /> Why this song
      </h4>
      <ul>
        {reasons.map((reason, index) => (
          <li key={index} className={`why-${reason.tone}`}>
            <WhyIcon reason={reason} />
            <span>{reason.text}</span>
          </li>
        ))}
      </ul>
      {math ? <WhyMaths math={math} /> : null}
    </div>
  );
}

// The optional, opt-in numeric breakdown: the group "base" score times every multiplier, landing
// on the final score the queue weights by. A higher score just means a higher chance of being
// picked next — it is not a percentage.
function WhyMaths(props: { math: ReturnType<typeof whyMath> }) {
  const math = props.math;
  if (!math) {
    return null;
  }
  const fmt = (value: number) => (Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2));
  return (
    <details className="why-maths" open>
      <summary>The maths</summary>
      <table>
        <tbody>
          <tr className="why-maths-base">
            <td>Group base</td>
            <td>{fmt(math.base)}</td>
          </tr>
          {math.rows.map((row) => (
            <tr key={row.label} className={row.neutral ? "why-maths-neutral" : ""}>
              <td>× {row.label}</td>
              <td>{fmt(row.value)}</td>
            </tr>
          ))}
          <tr className="why-maths-total">
            <td>= Score</td>
            <td>{fmt(math.score)}</td>
          </tr>
        </tbody>
      </table>
      <p className="why-maths-note">
        Score = group base × every factor above. A higher score means a higher chance of being
        picked next, not a percentage. Factors at 1.00 are neutral.
      </p>
    </details>
  );
}

function WhyIcon(props: { reason: WhyReason }) {
  switch (props.reason.icon) {
    case "star":
      return <Star size={14} />;
    case "spark":
      return <Sparkles size={14} />;
    case "video":
      return <Video size={14} />;
    case "history":
      return <Clock size={14} />;
    case "variant":
      return <ListMusic size={14} />;
    case "cooldown":
      return <Clock size={14} />;
    default:
      return <LibraryIcon size={14} />;
  }
}

function SavedRuns(props: {
  runs: RunSummary[] | null;
  currentRunId: number | null;
  onLoad: (id: number) => void;
  onRefresh: () => void;
  onRename: (id: number, name: string) => void;
  onDelete: (id: number) => void;
}) {
  if (props.runs === null) {
    return null;
  }
  if (props.runs.length === 0) {
    return <p className="saved-empty">Saved sessions will appear here.</p>;
  }
  function rename(run: RunSummary) {
    const name = window.prompt("Rename session", run.name ?? "")?.trim();
    if (name) {
      props.onRename(run.id, name);
    }
  }
  return (
    <div className="saved-runs">
      <div className="saved-head">
        <h5>Saved sessions</h5>
        <button className="link" onClick={props.onRefresh}>
          Refresh
        </button>
      </div>
      <ul>
        {props.runs.slice(0, 8).map((run) => (
          <li key={run.id} className={run.id === props.currentRunId ? "current" : ""}>
            <button className="saved-load" onClick={() => props.onLoad(run.id)}>
              <strong>{run.name || `Session #${run.id}`}</strong>
              <small>
                {run.item_count} tracks · {run.preview_titles.slice(0, 2).join(", ") || "—"}
              </small>
            </button>
            <div className="saved-actions">
              <button className="mini" title="Rename" onClick={() => rename(run)}>
                ✎
              </button>
              <button className="mini danger" title="Delete" onClick={() => props.onDelete(run.id)}>
                <Trash2 size={13} />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChipRow(props: { groups: TrackGroup[]; subGroup?: string | null }) {
  return (
    <div className="chip-row">
      {props.groups.slice(0, 4).map((group) => (
        <span key={group.id} className={`chip type-${group.group_type}`}>
          {group.name}
        </span>
      ))}
      {props.subGroup ? <span className="chip variant">↺ {props.subGroup}</span> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Library view
// ---------------------------------------------------------------------------

type Facet = { key: string; label: string; type: string; count: number };

function LibraryView(props: {
  tracks: Track[];
  tags: Tag[];
  onTagsChanged: () => void;
  ratingFactors: RatingFactor[];
  busy: boolean;
  currentTrackId: number | null;
  currentTime: number;
  youtubeEnabled: boolean;
  onSave: (track: Track) => Promise<Track>;
  onRate: (track: Track, factorKey: string, value: number | null) => void;
  onRescan: () => void;
}) {
  const [search, setSearch] = useState("");
  const [facet, setFacet] = useState<string>("all");
  const [manageTags, setManageTags] = useState(false);
  const [quick, setQuick] = useState<"all" | "video" | "unrated">("all");
  const [selected, setSelected] = useState<Track | null>(null);
  const [scanPath, setScanPath] = useState("");
  const [scanning, setScanning] = useState(false);

  const [groupBusy, setGroupBusy] = useState<string | null>(null);
  const facets = useMemo(() => buildFacets(props.tracks), [props.tracks]);

  // Reassign every track in `from` to `to` (rename when `to` is new, merge when it
  // already exists). De-dupes so a track never lists the same group twice.
  async function reassignGroup(from: string, to: string, groupType: string) {
    const clean = to.trim();
    if (!clean || clean === from) {
      return;
    }
    const affected = props.tracks.filter((track) => track.groups.some((group) => group.name === from));
    setGroupBusy(from);
    try {
      for (const track of affected) {
        const seen = new Set<string>();
        const groups = track.groups
          .map((group) => (group.name === from ? { ...group, name: clean, group_type: groupType } : group))
          .filter((group) => (seen.has(group.name) ? false : (seen.add(group.name), true)))
          .map((group) => ({ name: group.name, group_type: group.group_type, share: group.share ?? null }));
        await api.updateTrackFields(track.id, { groups });
      }
      props.onRescan();
    } finally {
      setGroupBusy(null);
    }
  }

  function renameGroup(name: string, type: string) {
    const next = window.prompt(`Rename group "${name}" to:`, name);
    if (next) {
      void reassignGroup(name, next, type);
    }
  }

  function mergeGroup(name: string, type: string) {
    const target = window.prompt(`Merge "${name}" into which group? (type the exact target name)`);
    if (target) {
      void reassignGroup(name, target, type);
    }
  }

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return props.tracks.filter((track) => {
      if (quick === "video" && !track.assets.some((asset) => asset.asset_type === "video")) {
        return false;
      }
      if (quick === "unrated" && Object.values(track.ratings).some((value) => value != null)) {
        return false;
      }
      if (facet !== "all") {
        const [type, name] = facet.split("::");
        if (type === "tag") {
          if (!(track.tags ?? []).includes(name)) {
            return false;
          }
        } else if (type === "variant") {
          if (track.sub_group !== name) {
            return false;
          }
        } else if (!track.groups.some((group) => group.group_type === type && group.name === name)) {
          return false;
        }
      }
      if (!needle) {
        return true;
      }
      return [
        track.title,
        track.artist,
        track.album,
        track.sub_group,
        ...track.groups.map((g) => g.name),
        ...(track.tags ?? [])
      ]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(needle));
    });
  }, [props.tracks, search, facet, quick]);

  async function scan() {
    if (!scanPath.trim()) {
      return;
    }
    setScanning(true);
    try {
      await api.scan(scanPath.trim());
      props.onRescan();
    } finally {
      setScanning(false);
    }
  }

  return (
    <section className="library-view">
      <aside className="facet-rail">
        <button className={facet === "all" ? "facet active" : "facet"} onClick={() => setFacet("all")}>
          All tracks <b>{props.tracks.length}</b>
        </button>
        <FacetGroup title="Sources" facets={facets.source} active={facet} busy={groupBusy} onPick={setFacet} onRename={renameGroup} onMerge={mergeGroup} />
        <FacetGroup title="Artists" facets={facets.artist} active={facet} busy={groupBusy} onPick={setFacet} onRename={renameGroup} onMerge={mergeGroup} />
        <FacetGroup title="Themes" facets={facets.theme} active={facet} busy={groupBusy} onPick={setFacet} onRename={renameGroup} onMerge={mergeGroup} />
        <FacetGroup title="Variant families" facets={facets.variant} active={facet} onPick={setFacet} />
        <FacetGroup title="Tags" facets={facets.tag} active={facet} onPick={setFacet} />
        <button className="facet manage-tags" onClick={() => setManageTags((open) => !open)}>
          {manageTags ? "Close tag manager" : "Manage tags…"}
        </button>
        {manageTags ? <TagManager tags={props.tags} onChanged={props.onTagsChanged} /> : null}
      </aside>

      <div className="library-main">
        <div className="library-toolbar">
          <label className="search-box">
            <Search size={16} />
            <input value={search} placeholder="Search title, artist, group…" onChange={(e) => setSearch(e.target.value)} />
          </label>
          <div className="quick-filters">
            {(["all", "video", "unrated"] as const).map((key) => (
              <button
                key={key}
                className={quick === key ? "quick active" : "quick"}
                onClick={() => setQuick(key)}
              >
                {key === "all" ? "All" : key === "video" ? "Video" : "Unrated"}
              </button>
            ))}
          </div>
          <div className="scan-box">
            <input value={scanPath} placeholder="Scan a folder…" onChange={(e) => setScanPath(e.target.value)} />
            <button className="primary" disabled={scanning} onClick={() => void scan()}>
              <Plus size={16} /> Scan
            </button>
          </div>
        </div>
        <div className="library-count">
          {filtered.length} of {props.tracks.length} tracks
        </div>

        <div className="track-list">
          {filtered.length === 0 ? (
            <div className="track-empty">No tracks match the current filter or search.</div>
          ) : (
            filtered.map((track) => (
              <button
                key={track.id}
                className={`track-card ${selected?.id === track.id ? "active" : ""} ${
                  (track.tags ?? []).includes("Ignored") ? "ignored" : ""
                }`}
                onClick={() => setSelected(track)}
              >
                <span className="track-art" style={artStyle(track.id)}>
                  {track.assets.some((asset) => asset.asset_type === "video") ? <Video size={16} /> : <ListMusic size={16} />}
                </span>
                <span className="track-main">
                  <strong>{track.title}</strong>
                  <small>{displayArtist(track) || "—"}</small>
                </span>
                <span className="track-groups">
                  {track.groups.slice(0, 3).map((group) => (
                    <span key={group.id} className={`chip type-${group.group_type}`}>
                      {group.name}
                    </span>
                  ))}
                  {track.sub_group ? <span className="chip variant">↺</span> : null}
                </span>
                <MiniRating value={track.ratings.overall ?? null} />
              </button>
            ))
          )}
        </div>
      </div>

      {selected ? (
        <TrackEditor
          key={selected.id}
          track={selected}
          tags={props.tags}
          factors={props.ratingFactors}
          busy={props.busy}
          isCurrent={props.currentTrackId === selected.id}
          currentTime={props.currentTime}
          youtubeEnabled={props.youtubeEnabled}
          onSave={async (draft) => setSelected(await props.onSave(draft))}
          onRate={props.onRate}
          onClose={() => setSelected(null)}
        />
      ) : (
        <div className="editor-empty">
          <Star size={30} />
          <p>Select a track to edit details and ratings.</p>
        </div>
      )}
    </section>
  );
}

function FacetGroup(props: {
  title: string;
  facets: Facet[];
  active: string;
  busy?: string | null;
  onPick: (key: string) => void;
  onRename?: (name: string, type: string) => void;
  onMerge?: (name: string, type: string) => void;
}) {
  if (props.facets.length === 0) {
    return null;
  }
  const editable = Boolean(props.onRename && props.onMerge);
  return (
    <div className="facet-group">
      <h5>{props.title}</h5>
      {props.facets.map((entry) => (
        <div key={entry.key} className={`facet-item ${props.busy === entry.label ? "busy" : ""}`}>
          <button
            className={props.active === entry.key ? "facet active" : "facet"}
            onClick={() => props.onPick(entry.key)}
          >
            {entry.label} <b>{entry.count}</b>
          </button>
          {editable ? (
            <div className="facet-ops">
              <button className="mini" title="Rename group" onClick={() => props.onRename!(entry.label, entry.type)}>
                <Pencil size={12} />
              </button>
              <button className="mini" title="Merge into another group" onClick={() => props.onMerge!(entry.label, entry.type)}>
                <GitMerge size={12} />
              </button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

// Rename, delete, and flag custom tags. System tags (Favourite, Ignored) are fixed.
function TagManager(props: { tags: Tag[]; onChanged: () => void }) {
  const [name, setName] = useState("");
  async function run(action: Promise<unknown>) {
    try {
      await action;
    } finally {
      props.onChanged();
    }
  }
  return (
    <div className="tag-manager">
      {props.tags.map((tag) => (
        <div key={tag.id} className="tag-row">
          <span className="tag-name">
            {tag.name} <b>{tag.track_count}</b>
          </span>
          {tag.kind === "system" ? (
            <small>built-in</small>
          ) : (
            <span className="tag-ops">
              <label title="Assignments are shared by every profile in the household">
                <input
                  type="checkbox"
                  checked={tag.shared}
                  onChange={(e) => void run(api.updateTag(tag.id, { shared: e.target.checked }))}
                />
                shared
              </label>
              <label title="Feeds the tag pacing bias in Settings">
                <input
                  type="checkbox"
                  checked={tag.affects_algorithm}
                  onChange={(e) =>
                    void run(api.updateTag(tag.id, { affects_algorithm: e.target.checked }))
                  }
                />
                algorithm
              </label>
              <button
                className="mini"
                title="Rename tag"
                onClick={() => {
                  const next = window.prompt(`Rename tag "${tag.name}" to:`, tag.name)?.trim();
                  if (next && next !== tag.name) {
                    void run(api.updateTag(tag.id, { name: next }));
                  }
                }}
              >
                <Pencil size={12} />
              </button>
              <button
                className="mini"
                title="Delete tag"
                onClick={() => {
                  if (window.confirm(`Delete the tag "${tag.name}"? Its assignments go too.`)) {
                    void run(api.deleteTag(tag.id));
                  }
                }}
              >
                <X size={12} />
              </button>
            </span>
          )}
        </div>
      ))}
      <div className="new-tag-row">
        <input
          value={name}
          placeholder="New tag name…"
          onChange={(e) => setName(e.target.value)}
        />
        <button
          className="mini-text"
          onClick={() => {
            const clean = name.trim();
            if (clean) {
              setName("");
              void run(api.createTag({ name: clean }));
            }
          }}
        >
          Add
        </button>
      </div>
    </div>
  );
}

// Read-only stars with partial fill, for displaying a fractional average rating.
function FractionalStars(props: { value: number; size?: number }) {
  const size = props.size ?? 12;
  const value = Math.min(Math.max(props.value, 0), 5);
  return (
    <span className="frac-stars" style={{ display: "inline-flex", gap: 1 }}>
      {[0, 1, 2, 3, 4].map((i) => {
        const fill = Math.min(Math.max(value - i, 0), 1);
        return (
          <span key={i} style={{ position: "relative", width: size, height: size, display: "inline-block" }}>
            <Star size={size} fill="none" style={{ position: "absolute", inset: 0 }} />
            {fill > 0 ? (
              <span
                style={{ position: "absolute", inset: 0, width: `${fill * 100}%`, overflow: "hidden" }}
              >
                <Star size={size} fill="currentColor" />
              </span>
            ) : null}
          </span>
        );
      })}
    </span>
  );
}

function MiniRating(props: { value: number | null }) {
  if (props.value == null) {
    return <span className="mini-rating unrated">Unrated</span>;
  }
  return (
    <span className="mini-rating" title={`Average overall ${props.value.toFixed(1)}/5`}>
      <FractionalStars value={props.value} size={12} />
      <em>{props.value.toFixed(1)}</em>
    </span>
  );
}

// Shows the A/B comparison state of a cover set and lets the user reopen a settled ranking. The
// per-rendition strength is relative within the set (higher = preferred); it is never an absolute
// star, matching the "performance is relative" design.
function CoverSetPanel(props: { subGroup: string }) {
  const [state, setState] = useState<CoverSetRead | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .coverSet(props.subGroup)
      .then((value) => {
        if (!cancelled) setState(value);
      })
      .catch(() => {
        /* status is informational; ignore if unavailable */
      });
    return () => {
      cancelled = true;
    };
  }, [props.subGroup]);

  if (!state) {
    return null;
  }
  const phaseLabel =
    state.comparison_phase === "settled"
      ? "Ranking settled"
      : state.comparison_phase === "bootstrapping"
        ? "Comparing versions"
        : "Not yet compared";

  async function reopen() {
    setBusy(true);
    try {
      setState(await api.reopenCoverSet(props.subGroup));
    } catch {
      /* leave the current state if the reopen fails */
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="editor-section">
      <h5>Versions (covers)</h5>
      <p className="cover-status">
        {phaseLabel} · {state.total_comparisons} comparison
        {state.total_comparisons === 1 ? "" : "s"} across {state.renditions.length} version
        {state.renditions.length === 1 ? "" : "s"}
      </p>
      {state.comparison_phase === "settled" ? (
        <button className="link" disabled={busy} onClick={reopen}>
          Compare again
        </button>
      ) : null}
    </div>
  );
}

// A watch URL for an existing embed, so the editor shows the actual link. Prefers the stored
// URL; otherwise rebuilds one from the video id and start offset.
function youtubeLinkFor(embed: TrackEmbed | null): string {
  if (!embed) {
    return "";
  }
  if (embed.url) {
    return embed.url;
  }
  const base = `https://www.youtube.com/watch?v=${embed.external_id}`;
  return embed.start_seconds ? `${base}&t=${Math.floor(embed.start_seconds)}s` : base;
}

function TrackEditor(props: {
  track: Track;
  tags: Tag[];
  factors: RatingFactor[];
  busy: boolean;
  isCurrent: boolean;
  currentTime: number;
  youtubeEnabled: boolean;
  onSave: (track: Track) => void;
  onRate: (track: Track, factorKey: string, value: number | null) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<Track>(props.track);
  // The YouTube link is edited as raw text; the backend parses it into a structured embed on save.
  const existingYouTube = youtubeEmbedFor(props.track);
  const [youtubeLink, setYoutubeLink] = useState(youtubeLinkFor(existingYouTube));
  useEffect(() => {
    setDraft(props.track);
    setYoutubeLink(youtubeLinkFor(youtubeEmbedFor(props.track)));
  }, [props.track]);

  function update<K extends keyof Track>(key: K, value: Track[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  const [newTag, setNewTag] = useState("");
  function toggleTag(name: string) {
    setDraft((current) => {
      const cur = current.tags ?? [];
      const next = cur.includes(name) ? cur.filter((t) => t !== name) : [...cur, name];
      // Favourite rides in both places; keep the star in step with the chip.
      const favourite = name === "Favourite" ? next.includes("Favourite") : current.favourite;
      return { ...current, tags: next, favourite };
    });
  }

  function save() {
    // Send the link as a bare URL so the backend re-parses it every time (which handles an
    // edited link correctly, and reads any start time out of it). Blank clears the embed.
    const link = youtubeLink.trim();
    const embeds: Embed[] = link
      ? [{ id: existingYouTube?.id ?? 0, provider: "youtube", external_id: "", url: link, start_seconds: null }]
      : [];
    props.onSave({ ...draft, embeds });
  }

  const hasVideoAsset = draft.assets.some((asset) => asset.asset_type === "video");

  const applicable = useMemo(
    () => props.factors.filter((factor) => isFactorApplicable(factor, draft)),
    [props.factors, draft]
  );

  return (
    <aside className="track-editor">
      <div className="editor-header">
        <div>
          <h3>{draft.title}</h3>
          <small>{displayArtist(draft) || "Unknown artist"}</small>
        </div>
        <button
          className={`icon-button ghost favourite-toggle ${draft.favourite ? "on" : ""}`}
          title="Favourite"
          aria-label="Favourite"
          aria-pressed={draft.favourite ?? false}
          onClick={() => toggleTag("Favourite")}
        >
          <Star size={18} fill={draft.favourite ? "currentColor" : "none"} />
        </button>
        <button className="icon-button ghost" title="Close" onClick={props.onClose}>
          <X size={18} />
        </button>
      </div>

      <div className="editor-section">
        <h5>Ratings</h5>
        <p className="editor-hint">Stars show your running average.</p>
        <div className="rating-grid">
          {applicable.map((factor) => (
            <StarRating
              key={factor.key}
              label={factor.label}
              value={draft.ratings[factor.key] ?? null}
              onChange={(value) => {
                // Optimistically reflect the tap, then record it as a new data point.
                setDraft((current) => ({
                  ...current,
                  ratings: { ...current.ratings, [factor.key]: value }
                }));
                props.onRate(props.track, factor.key, value);
              }}
            />
          ))}
        </div>
      </div>

      <div className="editor-section">
        <h5>Details</h5>
        <div className="editor-grid">
          <label>
            Title
            <input value={draft.title} onChange={(e) => update("title", e.target.value)} />
          </label>
          <label>
            Artist
            <input value={draft.artist ?? ""} onChange={(e) => update("artist", e.target.value)} />
          </label>
          <label>
            Album
            <input value={draft.album ?? ""} onChange={(e) => update("album", e.target.value)} />
          </label>
          <label>
            Variant family
            <input
              value={draft.sub_group ?? ""}
              placeholder="e.g. dubs of one song"
              onChange={(e) => update("sub_group", e.target.value || null)}
            />
          </label>
          {draft.sub_group ? (
            <label className="check-line">
              <input
                type="checkbox"
                checked={draft.is_original_rendition ?? false}
                onChange={(e) => update("is_original_rendition", e.target.checked)}
              />
              Original rendition (slightly favoured among versions)
            </label>
          ) : null}
          <label className="check-line">
            <input type="checkbox" checked={draft.has_lyrics} onChange={(e) => update("has_lyrics", e.target.checked)} />
            Has lyrics
          </label>
          <label>
            Manual weight
            <input
              type="number"
              step="0.05"
              value={draft.manual_multiplier}
              onChange={(e) => update("manual_multiplier", Number(e.target.value))}
            />
          </label>
          <label className="wide">
            Groups <span className="hint">semicolon separated</span>
            <input
              value={draft.groups.map((group) => group.name).join("; ")}
              onChange={(e) => update("groups", parseGroups(e.target.value, draft.groups))}
            />
          </label>
        </div>
      </div>

      <div className="editor-section">
        <h5>Tags</h5>
        <div className="tag-chips">
          {[
            ...props.tags.filter((tag) => tag.kind === "custom").map((tag) => tag.name),
            ...(draft.tags ?? []).filter(
              (name) =>
                name !== "Favourite" &&
                name !== "Ignored" &&
                !props.tags.some((tag) => tag.name === name)
            )
          ].map((name) => {
            const on = (draft.tags ?? []).includes(name);
            return (
              <button
                key={name}
                className={`chip toggle ${on ? "on" : ""}`}
                onClick={() => toggleTag(name)}
              >
                {name}
              </button>
            );
          })}
        </div>
        <div className="new-tag-row">
          <input
            value={newTag}
            placeholder="New tag…"
            onChange={(e) => setNewTag(e.target.value)}
          />
          <button
            className="mini-text"
            onClick={() => {
              const clean = newTag.trim();
              if (clean) {
                setNewTag("");
                toggleTag(clean);
              }
            }}
          >
            Add
          </button>
        </div>
        <label className="check-line">
          <input
            type="checkbox"
            checked={(draft.tags ?? []).includes("Ignored")}
            onChange={() => toggleTag("Ignored")}
          />
          Ignored: never included in generated queues (manual play still works)
        </label>
      </div>

      {draft.sub_group ? <CoverSetPanel subGroup={draft.sub_group} /> : null}

      <div className="editor-section">
        <h5>Playback</h5>
        {hasVideoAsset ? (
          <label className="check-line">
            <input
              type="checkbox"
              checked={draft.audio_only ?? false}
              onChange={(e) => update("audio_only", e.target.checked)}
            />
            Audio only: hide the video, keep the sound
          </label>
        ) : null}
        <div className="trim-grid">
          <TrimField
            label="Trim in"
            value={draft.clip_start_seconds ?? null}
            isCurrent={props.isCurrent}
            currentTime={props.currentTime}
            onChange={(value) => update("clip_start_seconds", value)}
          />
          <TrimField
            label="Trim out"
            value={draft.clip_end_seconds ?? null}
            isCurrent={props.isCurrent}
            currentTime={props.currentTime}
            onChange={(value) => update("clip_end_seconds", value)}
          />
        </div>
        <small className="trim-note">
          Non-destructive: playback just skips the intro/outro. The unused parts stay on disk for now.
        </small>
        {props.youtubeEnabled ? (
          <label className="wide youtube-link-field">
            YouTube link <span className="hint">plays via YouTube's official player</span>
            <input
              value={youtubeLink}
              placeholder="https://www.youtube.com/watch?v=…"
              onChange={(e) => setYoutubeLink(e.target.value)}
            />
            <small>
              A start time in the link (for example t=30s) is kept as the trim-in point. Leave blank
              to remove.
            </small>
          </label>
        ) : null}
      </div>

      <div className="editor-section">
        <h5>Media</h5>
        <div className="asset-list">
          {draft.assets.map((asset) => (
            <div key={asset.id} className="asset-row">
              <span className={`asset-type ${asset.asset_type}`}>{asset.asset_type}</span>
              <code>{asset.container ?? asset.codec ?? "file"}</code>
              {asset.is_lossless ? <span className="tag">lossless</span> : null}
            </div>
          ))}
          {draft.assets.length === 0 ? <small>No media files linked.</small> : null}
        </div>
      </div>

      <button className="primary save-button" disabled={props.busy} onClick={save}>
        <Save size={16} /> Save changes
      </button>
    </aside>
  );
}

function TrimField(props: {
  label: string;
  value: number | null;
  isCurrent: boolean;
  currentTime: number;
  onChange: (value: number | null) => void;
}) {
  return (
    <label className="trim-field">
      {props.label}
      <div className="trim-input">
        <input
          type="number"
          min={0}
          step={0.5}
          placeholder="—"
          value={props.value ?? ""}
          onChange={(event) =>
            props.onChange(event.target.value === "" ? null : Number(event.target.value))
          }
        />
        {props.isCurrent ? (
          <button
            type="button"
            className="mini-text"
            title="Set to the current playback position"
            onClick={() => props.onChange(Math.round(props.currentTime * 10) / 10)}
          >
            now
          </button>
        ) : null}
        {props.value != null ? (
          <button type="button" className="mini-text ghost" title="Clear" onClick={() => props.onChange(null)}>
            <X size={12} />
          </button>
        ) : null}
      </div>
      <small>{props.value != null ? formatTime(props.value) : "not set"}</small>
    </label>
  );
}

function StarRating(props: { label: string; value: number | null; onChange: (value: number | null) => void }) {
  // The value shown is the running AVERAGE (fractional); tapping a star adds a new rating.
  const rounded = props.value != null ? Math.round(props.value) : null;
  const isFractional = props.value != null && Math.abs(props.value - (rounded ?? 0)) > 0.05;
  return (
    <div className="star-rating">
      <span>{props.label}</span>
      <div>
        {[1, 2, 3, 4, 5].map((value) => (
          <button
            key={value}
            className={rounded != null && value <= rounded ? "active" : ""}
            title={`Rate ${props.label} ${value}`}
            onClick={() => props.onChange(value)}
          >
            <Star size={15} fill={rounded != null && value <= rounded ? "currentColor" : "none"} />
          </button>
        ))}
        {props.value != null ? (
          <em className="star-avg" title="Your average rating">
            {props.value.toFixed(1)}
            {isFractional ? " avg" : ""}
          </em>
        ) : null}
        <button className="clear" title="Clear all ratings" onClick={() => props.onChange(null)}>
          <X size={12} />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stats view
// ---------------------------------------------------------------------------

function StatsView(props: { stats: StatsSummary; tracks: Track[]; events: PlaybackEvent[] }) {
  const { stats } = props;
  const playedIds = useMemo(
    () => new Set(props.events.filter((e) => e.event_type !== "paused").map((e) => e.track_id)),
    [props.events]
  );
  const decided = stats.completed_count + stats.skipped_count;
  const completionRate = decided > 0 ? pct(stats.completed_count, decided) : 0;
  const topGroups = useMemo(() => topGroupsByCount(props.tracks), [props.tracks]);
  const mostPlayed = useMemo(() => mostPlayedTracks(props.events, props.tracks), [props.events, props.tracks]);
  const health = useMemo(() => listeningHealth(props.events), [props.events]);

  return (
    <section className="stats-view">
      <div className="stat-cards">
        <StatCard label="Library" value={stats.track_count} hint="tracks" />
        <StatCard label="Coverage" value={`${pct(stats.rated_track_count, stats.track_count)}%`} hint={`${stats.rated_track_count} rated`} />
        <StatCard label="Heard at least once" value={`${pct(playedIds.size, stats.track_count)}%`} hint={`${playedIds.size} tracks`} />
        <StatCard label="Visual tracks" value={stats.video_track_count} hint="with video" />
        <StatCard label="This week" value={formatClock(health.weekSeconds)} hint="listening time" />
        <StatCard label="Completion rate" value={`${completionRate}%`} hint={`${stats.completed_count} finished`} />
      </div>

      <div className="stat-panels">
        <div className="stat-panel">
          <h4>Listening coverage</h4>
          <CoverageBar label="Rated" value={stats.rated_track_count} total={stats.track_count} tone="boost" />
          <CoverageBar label="Heard" value={playedIds.size} total={stats.track_count} tone="neutral" />
          <CoverageBar label="Still unrated" value={stats.unrated_track_count} total={stats.track_count} tone="suppress" />
          <p className="stat-note">
            Cold-start keeps surfacing unrated tracks until every song has had a fair chance. Coverage should
            climb steadily before anything repeats heavily.
          </p>
        </div>

        <div className="stat-panel">
          <h4>How sessions go</h4>
          <CoverageBar label="Completed" value={stats.completed_count} total={Math.max(decided, 1)} tone="boost" />
          <CoverageBar label="Skipped" value={stats.skipped_count} total={Math.max(decided, 1)} tone="suppress" />
          <div className="skip-split">
            <span>Early skips <b>{stats.early_skip_count}</b></span>
            <span>Partial skips <b>{stats.partial_skip_count}</b></span>
          </div>
          <p className="stat-note">
            Early skips (under 10% heard) count as a negative signal; partial skips count as half a listen.
          </p>
        </div>

        <div className="stat-panel">
          <h4>Biggest groups</h4>
          <BarList rows={topGroups} />
        </div>

        <div className="stat-panel">
          <h4>Most played</h4>
          {mostPlayed.length === 0 ? (
            <p className="stat-note">Nothing played yet. Generate a queue and press play.</p>
          ) : (
            <BarList rows={mostPlayed} />
          )}
        </div>

        <div className="stat-panel">
          <h4>Listening health</h4>
          {health.samples === 0 ? (
            <p className="stat-note">
              Loudness is measured live while you listen. Play a few tracks and your average and peak levels
              will appear here. They are relative estimates, not exact measurements.
            </p>
          ) : (
            <>
              <CoverageBar label="Average loudness" value={Math.round(health.avg * 100)} total={100} tone={health.avg > 0.75 ? "suppress" : "neutral"} />
              <CoverageBar label="Peak loudness" value={Math.round(health.peak * 100)} total={100} tone={health.peak > 0.92 ? "suppress" : "neutral"} />
              <CoverageBar label="Weekly exposure" value={Math.min(health.dosePct, 100)} total={100} tone={health.dosePct > 100 ? "suppress" : "boost"} />
              <p className="stat-note">
                Relative estimates, not calibrated dB, because browsers can't read true sound pressure. The{" "}
                <a href="https://www.who.int/activities/making-listening-safe" target="_blank" rel="noreferrer">
                  WHO
                </a>{" "}
                suggests ~80&nbsp;dB for 40&nbsp;h/week as a safe ceiling; each +3&nbsp;dB halves the safe
                time. Treat these as a nudge, not a measurement.
              </p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function StatCard(props: { label: string; value: number | string; hint: string }) {
  return (
    <div className="stat-card">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
      <small>{props.hint}</small>
    </div>
  );
}

function CoverageBar(props: { label: string; value: number; total: number; tone: WhyReason["tone"] }) {
  const ratio = props.total > 0 ? props.value / props.total : 0;
  return (
    <div className="coverage-bar">
      <div className="coverage-label">
        <span>{props.label}</span>
        <b>{props.value}</b>
      </div>
      <div className="coverage-track">
        <div className={`coverage-fill tone-${props.tone}`} style={{ width: `${Math.min(ratio * 100, 100)}%` }} />
      </div>
    </div>
  );
}

function BarList(props: { rows: { label: string; value: number }[] }) {
  const max = Math.max(...props.rows.map((row) => row.value), 1);
  return (
    <div className="bar-list">
      {props.rows.map((row) => (
        <div key={row.label} className="bar-row">
          <span className="bar-label" title={row.label}>
            {row.label}
          </span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(row.value / max) * 100}%` }} />
          </div>
          <b>{row.value}</b>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings view
// ---------------------------------------------------------------------------

// Individual keys that are complex even inside an otherwise-simple section. These are the
// fine-tuning knobs beside a plain everyday toggle: they stay hidden until "Show complex
// settings" is ticked, while the toggle they sit next to stays visible.
const ADVANCED_KEYS = new Set<string>([
  "cold_start_unrated_boost",
  "visual_priority_multiplier",
  "loudness_warning_level"
]);

const SETTING_SECTIONS: {
  title: string;
  note: string | JSX.Element;
  cosmetic?: boolean;
  // Whole-section complexity: when true, every control in the section is hidden until "Show
  // complex settings" is ticked. Simpler than tagging each key. Mixed sections leave this off
  // and rely on ADVANCED_KEYS for the odd complex knob instead.
  advanced?: boolean;
  keys: string[];
  // Optional richer guidance rendered as a block below the controls (for setup steps that need
  // more than a one-line note, e.g. enabling YouTube playback).
  extra?: JSX.Element;
}[] = [
  {
    title: "Queue",
    note: "How many songs a freshly generated queue holds.",
    keys: ["default_playlist_length"]
  },
  {
    title: "Recommendation core",
    note: "How strongly groups and your ratings shape the queue.",
    advanced: true,
    keys: [
      "beta",
      "enable_group_rating_multiplier",
      "song_rating_min_multiplier",
      "song_rating_max_multiplier"
    ]
  },
  {
    title: "Anti-repetition & variety",
    note: "How quickly a just-played song, group, or variant is allowed back.",
    advanced: true,
    keys: [
      "group_cooldown_floor",
      "sub_group_cooldown_floor",
      "group_clustering_bias",
      "tag_clustering_bias"
    ]
  },
  {
    title: "History & feedback",
    note: "How your plays and skips steer the next session.",
    advanced: true,
    keys: ["history_influence_enabled", "skip_penalty_strength"]
  },
  {
    title: "Coverage (cold start)",
    note: "Making sure every song gets a fair first hearing. (This is advised if you have just imported a library without additional personalised rating information.)",
    keys: ["cold_start_enabled", "cold_start_unrated_boost"]
  },
  {
    title: "Visuals",
    note: "Giving priority to tracks with video when you are watching rather than merely listening.",
    keys: ["visual_priority_enabled", "visual_priority_multiplier"]
  },
  {
    title: "Hearing health",
    note: (
      <>
        Moderating loudness and listening fatigue, in line with the{" "}
        <a
          href="https://www.who.int/activities/making-listening-safe"
          target="_blank"
          rel="noreferrer"
        >
          WHO's safe-listening guidance
        </a>
        .
      </>
    ),
    keys: [
      "loudness_warning_enabled",
      "loudness_warning_level",
      "compressed_break_reminder",
      "avoid_consecutive_compressed"
    ]
  },
  {
    title: "Rating normalisation",
    note: "How repeat ratings are averaged and normalised before they steer the queue.",
    advanced: true,
    keys: [
      "rating_normalization_enabled",
      "rating_calibration_enabled",
      "rating_outlier_sd",
      "rating_session_mood_correction",
      "rating_session_min_songs",
      "rating_coverage_ready_fraction"
    ]
  },
  {
    title: "Repetition & rediscovery",
    note: "Avoid wearing a song out by over-playing it, and bring back dormant favourites.",
    advanced: true,
    keys: [
      "satiation_enabled",
      "satiation_strength",
      "satiation_window_days",
      "rediscovery_enabled",
      "rediscovery_strength",
      "rediscovery_halflife_days",
      "favourite_pacing_enabled",
      "favourite_pacing_strength"
    ]
  },
  {
    title: "Explanations",
    note: "How much detail the “why this song” panel shows while you listen.",
    cosmetic: true,
    keys: ["why_show_math"]
  },
  {
    title: "Covers",
    note: "When a song has several renditions, let the queue pick which one to play. (Off by default, turn it on if your library has covers.)",
    advanced: true,
    keys: ["cover_two_level_enabled", "cover_count_log_base", "cover_original_bonus"]
  },
  {
    title: "YouTube playback",
    note: (
      <>
        Off by default. When on, a song that has a YouTube link plays through YouTube's official
        player. Read the setup notes below before you enable it.
      </>
    ),
    keys: ["youtube_embed_enabled"],
    extra: (
      <details className="setup-disclosure">
        <summary>Setup notes: cookies, ads, and loudness</summary>
        <div className="setup-guidance">
          <h5>Before you turn this on</h5>
          <ul>
            <li>
              <b>Cookies and consent.</b> A song with a YouTube link plays in YouTube's official
              embedded player. Loading that player contacts YouTube and lets it set its own
              cookies, so Harmonica asks you to accept once before the first video appears.
              Nothing is requested from YouTube until then, and Harmonica itself stays
              cookie-light.
            </li>
            <li>
              <b>Ads and tracking are YouTube's, not ours.</b> The embedded player may show ads
              and will track you as YouTube normally does. Harmonica uses YouTube's own player and
              does not remove either, take the audio out, hide the video, or strip anything, as
              YouTube's terms require. Whether you block that tracking is your own choice in your
              own browser, for example with a content blocker such as uBlock Origin. Harmonica
              does not do it for you.
            </li>
            <li>
              <b>Loudness is levelled by YouTube.</b> YouTube evens out loudness across videos, a
              feature it calls "Stable Volume", and some clients add a voice boost. That is
              applied by YouTube, so Harmonica cannot switch it off for you. If the player's
              settings gear offers "Stable Volume" you can turn it off there. Otherwise it is
              controlled in your YouTube account. Worth knowing if you would rather hear a track's
              original dynamics than a levelled loudness.
            </li>
          </ul>
          <p className="setup-how">
            To use it, paste a list of YouTube links on the Curate page to bring in many songs at
            once, or open one song in the library editor and paste its link. The optional Data API
            key, for metadata lookups only, is set on the server and never in the browser, and is
            not needed just to play a linked video.
          </p>
        </div>
      </details>
    )
  },
  {
    title: "Spotify",
    note: (
      <>
        Off by default. When on with app credentials set on the server, the Curate tab can read a
        public Spotify playlist and show which of its songs you already have. The daemon reads
        Spotify, so your browser never contacts it. Track names only, through Spotify's Web API. No
        audio is downloaded.
      </>
    ),
    keys: ["spotify_enabled"]
  },
  {
    title: "Device profiles",
    note: (
      <>
        What creating a new profile in the panel to the right may see. Off keeps the song list
        hidden from whoever is creating a profile, which matters when this install is shared over
        a network.
      </>
    ),
    keys: ["profile_song_picker_enabled"]
  }
];

// Appearance is a device-side preference (localStorage + CSS variables), not a server
// setting: it applies immediately and is not part of the Apply-changes draft.
function AppearanceSection() {
  const [theme, setTheme] = useState<ThemeSelection>(loadTheme);
  const activePreset = matchThemePreset(theme);

  function update(patch: Partial<ThemeSelection>) {
    setTheme((current) => {
      const next = { ...current, ...patch };
      applyTheme(next);
      saveTheme(next);
      return next;
    });
  }

  return (
    <div className="settings-section">
      <div className="section-head">
        <h4>Appearance</h4>
        <p>
          Colours for this device. They apply immediately, with no need to press Apply changes.
          The choices are limited on purpose, so text stays readable on every combination.
          <em className="cosmetic-tag">cosmetic</em>
        </p>
      </div>
      <div className="theme-presets" role="group" aria-label="Appearance presets">
        {THEME_PRESETS.map((preset) => {
          const preview = themePresetPreview(preset);
          return (
            <button
              key={preset.key}
              type="button"
              className={preset.key === activePreset ? "theme-preset active" : "theme-preset"}
              aria-pressed={preset.key === activePreset}
              onClick={() => update({ ...preset.selection })}
            >
              <span className="theme-preset-swatches" aria-hidden="true">
                <span className="theme-preset-dot" style={{ background: preview.surface }} />
                <span className="theme-preset-dot" style={{ background: preview.sidebar }} />
                <span className="theme-preset-dot" style={{ background: preview.playerbar }} />
              </span>
              {preset.name}
            </button>
          );
        })}
      </div>
      <div className="appearance-rows">
        <SwatchRow
          label="Background"
          options={SURFACE_OPTIONS.map((option) => ({ key: option.key, name: option.name, colour: option.bg }))}
          value={theme.surface}
          disabled={theme.dark}
          onPick={(key) => update({ surface: key })}
        />
        {theme.dark ? <p className="swatch-hint">Dark mode sets its own background.</p> : null}
        <SwatchRow
          label="Sidebar"
          options={BAR_OPTIONS.map((option) => ({ key: option.key, name: option.name, colour: option.base }))}
          value={theme.sidebar}
          onPick={(key) => update({ sidebar: key })}
        />
        <SwatchRow
          label="Player bar"
          options={BAR_OPTIONS.map((option) => ({ key: option.key, name: option.name, colour: option.base }))}
          value={theme.playerbar}
          onPick={(key) => update({ playerbar: key })}
        />
        <div className="swatch-row">
          <span className="swatch-label">Dark mode</span>
          <button
            className={theme.dark ? "switch-control on" : "switch-control"}
            onClick={() => update({ dark: !theme.dark })}
            role="switch"
            aria-checked={theme.dark}
            type="button"
          >
            <span className="switch-label">{theme.dark ? "On" : "Off"}</span>
            <span className="switch-track">
              <span className="switch-knob" />
            </span>
          </button>
        </div>
        {theme.dark ? (
          <>
            <SwatchRow
              label="Dark tone"
              options={DARK_TONES.map((option) => ({ key: option.key, name: option.name, colour: option.bg }))}
              value={theme.darkTone}
              onPick={(key) => update({ darkTone: key })}
            />
            <p className="swatch-hint">
              Neutral is a plain dark. Warm leans amber, which sits easier with night-time viewing.
              Green matches the classic look.
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}

function SwatchRow(props: {
  label: string;
  options: { key: string; name: string; colour: string }[];
  value: string;
  disabled?: boolean;
  onPick: (key: string) => void;
}) {
  const active = props.options.find((option) => option.key === props.value);
  return (
    <div className={props.disabled ? "swatch-row disabled" : "swatch-row"}>
      <span className="swatch-label">{props.label}</span>
      {props.options.map((option) => (
        <button
          key={option.key}
          className={option.key === props.value ? "swatch active" : "swatch"}
          style={{ background: option.colour }}
          title={option.name}
          aria-label={`${props.label}: ${option.name}`}
          aria-pressed={option.key === props.value}
          onClick={() => props.onPick(option.key)}
          type="button"
        />
      ))}
      <span className="swatch-name">{active?.name}</span>
    </div>
  );
}

// Whether the complex settings tier is shown. Per-device, like the theme, so it lives in
// localStorage rather than the server-side settings draft.
const SHOW_COMPLEX_KEY = "harmonica.settings.show-complex";

function loadShowComplex(): boolean {
  try {
    return localStorage.getItem(SHOW_COMPLEX_KEY) === "1";
  } catch {
    return false;
  }
}

function saveShowComplex(value: boolean): void {
  try {
    localStorage.setItem(SHOW_COMPLEX_KEY, value ? "1" : "0");
  } catch {
    /* private mode; the preference just won't persist. */
  }
}

function SettingsView(props: {
  settings: AppSettings;
  ratingFactors: RatingFactor[];
  busy: boolean;
  onSave: (values: Record<string, number | boolean>) => Promise<void>;
  guardRef: MutableRefObject<SettingsGuard | null>;
  onOpenCurate: () => void;
  configsEnabled: boolean;
  activeConfig: DeviceConfigDetail | null;
  allTracks: Track[];
  onClaim: (name: string, passphrase: string) => Promise<DeviceConfigDetail>;
  onCreate: (name: string, passphrase: string, trackIds: number[]) => Promise<DeviceConfigDetail>;
  onSwitchLocal: () => void;
  onImported: () => Promise<void> | void;
}) {
  const [draft, setDraft] = useState<Record<string, number | boolean>>(() => settingsToDraft(props.settings));
  useEffect(() => setDraft(settingsToDraft(props.settings)), [props.settings]);
  const [showComplex, setShowComplex] = useState<boolean>(loadShowComplex);

  function toggleComplex() {
    setShowComplex((current) => {
      const next = !current;
      saveShowComplex(next);
      return next;
    });
  }

  const dirty = useMemo(
    () => props.settings.controls.some((control) => draft[control.key] !== props.settings[control.key]),
    [draft, props.settings]
  );
  const activePreset = useMemo(() => matchPreset(draft), [draft]);

  // Register the draft state with the app shell so leaving Settings can ask about it.
  useEffect(() => {
    props.guardRef.current = {
      dirty,
      apply: () => props.onSave(draft),
      discard: () => setDraft(settingsToDraft(props.settings))
    };
    return () => {
      props.guardRef.current = null;
    };
  });

  // Closing or reloading the tab with unapplied changes gets the browser's own confirmation.
  useEffect(() => {
    if (!dirty) {
      return;
    }
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const controlsByKey = useMemo(
    () => new Map(props.settings.controls.map((control) => [control.key as string, control])),
    [props.settings.controls]
  );
  const known = new Set(SETTING_SECTIONS.flatMap((section) => section.keys));
  const extraKeys = props.settings.controls.map((c) => c.key as string).filter((key) => !known.has(key));

  function applyPreset(preset: Preset) {
    // Stage the preset into the draft; nothing takes effect until "Apply changes" is clicked.
    setDraft((current) => ({ ...current, ...preset.values }));
  }

  function renderControls(keys: string[]) {
    return keys
      .map((key) => controlsByKey.get(key))
      .filter((control): control is SettingControl => Boolean(control))
      .map((control) => (
        <SettingControlRow
          key={control.key}
          control={control}
          value={draft[control.key]}
          onChange={(value) => setDraft((current) => ({ ...current, [control.key]: value }))}
        />
      ));
  }

  // Which of a section's keys to render given the current tier. Hiding is display-only: the
  // draft still holds every value, so Apply changes, the leave guard and Reset cover the hidden
  // controls too.
  function visibleKeys(section: (typeof SETTING_SECTIONS)[number]): string[] {
    if (showComplex) {
      return section.keys;
    }
    if (section.advanced) {
      return [];
    }
    return section.keys.filter((key) => !ADVANCED_KEYS.has(key));
  }

  return (
    <section className="settings-view">
      <div className="settings-main">
        <div className="preset-card">
          <div className="preset-head">
            <h4>Listening presets</h4>
            <p>A preset sets every control below. You can still fine-tune afterwards.</p>
          </div>
          <div className="preset-grid">
            {PRESETS.map((preset) => (
              <button
                key={preset.key}
                className={`preset ${activePreset === preset.key ? "active" : ""}`}
                onClick={() => applyPreset(preset)}
                title={preset.description}
              >
                <strong>{preset.name}</strong>
                <small>{preset.tagline}</small>
              </button>
            ))}
          </div>
          {activePreset ? (
            <p className="preset-active">
              {PRESETS.find((preset) => preset.key === activePreset)?.description}
            </p>
          ) : (
            <p className="preset-active custom">Custom: adjust any control, or pick a preset to start afresh.</p>
          )}
        </div>

        {SETTING_SECTIONS.map((section) => {
          const keys = visibleKeys(section);
          if (!keys.length) {
            return null;
          }
          return (
            <div key={section.title} className="settings-section">
              <div className="section-head">
                <h4>{section.title}</h4>
                <p>
                  {section.note}
                  {section.cosmetic ? <em className="cosmetic-tag">cosmetic</em> : null}
                </p>
              </div>
              <div className="settings-controls">{renderControls(keys)}</div>
              {section.extra}
              {section.title === "YouTube playback" && draft.youtube_embed_enabled ? (
                <div className="setup-guidance">
                  <h5>YouTube playback is on</h5>
                  <p>
                    Paste a list of YouTube links on the{" "}
                    <button className="link-button" onClick={props.onOpenCurate}>
                      Curate page
                    </button>{" "}
                    and each link becomes a song, or open one song in the library editor and paste
                    its link there.{dirty ? " Apply your changes first." : ""}
                  </p>
                  <ul>
                    <li>
                      <b>Importing reads each video's properties.</b> Harmonica reads the links'
                      metadata on the server, the uploader and title by default and more with a
                      Data API key, and organises them into tracks. Nothing is downloaded.
                    </li>
                    <li>
                      <b>You review before anything lands.</b> The organised tracks appear as a
                      proposal on the Curate page, where you check them and apply the ones you
                      accept.
                    </li>
                    <li>
                      <b>Playback stays official.</b> Each imported song plays through YouTube's
                      own embedded player.
                    </li>
                  </ul>
                </div>
              ) : null}
            </div>
          );
        })}

        <AppearanceSection />

        {showComplex && extraKeys.length ? (
          <div className="settings-section">
            <div className="section-head">
              <h4>More</h4>
            </div>
            <div className="settings-controls">{renderControls(extraKeys)}</div>
          </div>
        ) : null}
      </div>

      <div className="settings-side">
        {dirty ? (
          <button className="primary save-button" disabled={props.busy} onClick={() => props.onSave(draft)}>
            <Save size={16} /> Apply changes
          </button>
        ) : (
          <div className="save-button applied" role="status" aria-live="polite">
            <Check size={16} /> Saved
          </div>
        )}
        <div className="complex-toggle">
          <div className="complex-toggle-copy">
            <strong>Show complex settings</strong>
            <p>Off keeps the list to the everyday controls. On reveals the fine-tuning knobs.</p>
          </div>
          <button
            className={showComplex ? "switch-control on" : "switch-control"}
            onClick={toggleComplex}
            role="switch"
            aria-checked={showComplex}
            type="button"
          >
            <span className="switch-label">{showComplex ? "On" : "Off"}</span>
            <span className="switch-track">
              <span className="switch-knob" />
            </span>
          </button>
        </div>
        <button
          className="reset-defaults"
          onClick={() =>
            setDraft((current) => {
              const next = { ...current };
              for (const control of props.settings.controls) {
                next[control.key] = control.default;
              }
              return next;
            })
          }
        >
          <RotateCcw size={14} /> Reset all settings to defaults
        </button>
        {props.configsEnabled ? (
          <DeviceProfilePanel
            activeConfig={props.activeConfig}
            allTracks={props.allTracks}
            songPicker={Boolean(props.settings.profile_song_picker_enabled)}
            onClaim={props.onClaim}
            onCreate={props.onCreate}
            onSwitchLocal={props.onSwitchLocal}
          />
        ) : null}
        <BackupPanel onImported={props.onImported} />
        <div className="backup-card">
          <h5>Curate</h5>
          <p>
            The Curate page is where you review an agent's organising proposal and bring in new
            songs. It is opened from here once your library has songs, since curation is an
            occasional act rather than a daily surface.
          </p>
          <div className="backup-buttons">
            <button type="button" onClick={props.onOpenCurate}>
              <ClipboardCheck size={13} /> Open the Curate page
            </button>
          </div>
        </div>
        <div className="settings-note">
          <h4>How settings apply</h4>
          <p>
            Changes affect the next queue you generate. Existing sessions keep the snapshot they were built with,
            so tweaking won't disturb what you're hearing now.
          </p>
        </div>
        <div className="factor-card">
          <h5>Rating factors</h5>
          {props.ratingFactors.map((factor) => (
            <div key={factor.key} className="factor-row">
              <span>{factor.label}</span>
              <small>{factor.applies_to_variants_only ? "variants" : factor.applies_to_lyrics ? "all" : "instrumental"}</small>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function summariseImport(summary: ImportSummary): string {
  const count = (n: number, single: string, plural: string) =>
    `${n} ${n === 1 ? single : plural}`;
  const parts: string[] = [];
  const songs = summary.tracks_created + summary.tracks_matched;
  if (songs) {
    parts.push(`${count(songs, "song", "songs")} (${summary.tracks_created} new)`);
  }
  if (summary.track_ratings_applied) {
    parts.push(count(summary.track_ratings_applied, "current star", "current stars"));
  }
  if (summary.rating_samples_added) {
    parts.push(
      count(summary.rating_samples_added, "rating history entry", "rating history entries")
    );
  }
  if (summary.cover_comparisons_added) {
    parts.push(count(summary.cover_comparisons_added, "cover verdict", "cover verdicts"));
  }
  if (summary.settings_applied) {
    parts.push(count(summary.settings_applied, "setting", "settings"));
  }
  if (summary.tracks_skipped) {
    parts.push(
      count(summary.tracks_skipped, "unreadable entry skipped", "unreadable entries skipped")
    );
  }
  if (!parts.length) {
    return "Nothing in that file applied to this library.";
  }
  return "Imported: " + parts.join(", ") + ".";
}

function BackupPanel(props: { onImported: () => Promise<void> | void }) {
  const [busyScope, setBusyScope] = useState<ExportScope | null>(null);
  const [importing, setImporting] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  async function exportScope(scope: ExportScope) {
    setBusyScope(scope);
    setNote(null);
    try {
      const payload = await api.exportLibraryScoped(scope);
      const stamp = new Date().toISOString().slice(0, 10);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `harmonica-${scope}-${stamp}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setNote(message(err, "The export could not be prepared."));
    } finally {
      setBusyScope(null);
    }
  }

  async function onFile(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setImporting(true);
    setNote(null);
    try {
      // The backend enforces the same cap; checking here saves uploading a doomed file.
      if (file.size > 64 * 1024 * 1024) {
        throw new Error("That file is larger than any Harmonica export.");
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(await file.text());
      } catch {
        throw new Error("That file is not a Harmonica export. It is not valid JSON.");
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("That file is not a Harmonica export.");
      }
      const summary = await api.importLibraryFile(parsed as Record<string, unknown>);
      setNote(summariseImport(summary));
      await props.onImported();
    } catch (err) {
      setNote(message(err, "The import failed."));
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const scopes: { scope: ExportScope; label: string }[] = [
    { scope: "metadata", label: "Metadata" },
    { scope: "ratings", label: "Ratings" },
    { scope: "settings", label: "Settings" },
    { scope: "all", label: "Everything" }
  ];

  return (
    <div className="backup-card">
      <h5>Export and import</h5>
      <p>
        Download your data as a file: the metadata (songs and groups), your ratings (stars and
        their history), your settings, or everything at once.
      </p>
      <div className="backup-buttons">
        {scopes.map(({ scope, label }) => (
          <button
            key={scope}
            type="button"
            disabled={busyScope !== null}
            onClick={() => void exportScope(scope)}
          >
            <Download size={13} /> {busyScope === scope ? "Preparing" : label}
          </button>
        ))}
      </div>
      <p>
        Importing a file adds what it holds and never deletes. A file can only add songs,
        ratings clamped to the star scale, and settings within each control's own range.
      </p>
      <label className={importing ? "backup-import busy" : "backup-import"}>
        <Upload size={13} /> {importing ? "Importing" : "Import an export file"}
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          hidden
          disabled={importing}
          onChange={(event) => void onFile(event.target.files)}
        />
      </label>
      {note ? (
        <p className="backup-note" role="status" aria-live="polite">
          {note}
        </p>
      ) : null}
    </div>
  );
}

function DeviceProfilePanel(props: {
  activeConfig: DeviceConfigDetail | null;
  allTracks: Track[];
  // Whether the create form may list the library for picking a subset (the
  // profile_song_picker_enabled setting). Off = new profiles include all songs, and the
  // library's song list is never shown to whoever is creating a profile.
  songPicker: boolean;
  onClaim: (name: string, passphrase: string) => Promise<DeviceConfigDetail>;
  onCreate: (name: string, passphrase: string, trackIds: number[]) => Promise<DeviceConfigDetail>;
  onSwitchLocal: () => void;
}) {
  const [mode, setMode] = useState<"claim" | "create">("claim");
  const [name, setName] = useState("");
  const [passphrase, setPassphrase] = useState("");
  // Pre-filling from the current library is opt-in twice over: the songPicker setting must be
  // on, and the creator must tick the box. Otherwise a new profile starts empty and imports.
  const [preFill, setPreFill] = useState(false);
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return props.allTracks;
    return props.allTracks.filter((track) =>
      `${track.title} ${track.artist ?? ""}`.toLowerCase().includes(needle)
    );
  }, [props.allTracks, search]);

  function reset() {
    setName("");
    setPassphrase("");
    setError(null);
    setPreFill(false);
    setChosen(new Set());
    setSearch("");
  }

  function toggle(id: number) {
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function submit() {
    if (!name.trim() || !passphrase.trim()) {
      setError("Name and passphrase are both required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (mode === "claim") {
        await props.onClaim(name.trim(), passphrase);
      } else {
        // No pre-fill (or picker off) = an empty profile that imports its own library.
        const filling = preFill && props.songPicker;
        const ids = filling ? [...chosen] : [];
        if (filling && ids.length === 0) {
          setError("Pick at least one song, or untick pre-filling.");
          setBusy(false);
          return;
        }
        await props.onCreate(name.trim(), passphrase, ids);
      }
      reset();
    } catch (err) {
      setError(
        message(err, mode === "claim" ? "Could not claim that profile." : "Could not create that profile.")
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="profile-panel">
      <div className="profile-head">
        <h4>
          <Smartphone size={15} /> Device profile
        </h4>
        <p>
          Optional. Share one library across devices. Each device claims its own profile (its songs and
          settings) by passphrase. Leave this be for normal single-device use.
        </p>
      </div>

      {props.activeConfig ? (
        <div className="profile-active">
          <div>
            <strong>{props.activeConfig.name}</strong>
            <small>
              {props.activeConfig.included_track_ids.length === 0
                ? "No songs yet"
                : `${props.activeConfig.included_track_ids.length} songs`}
            </small>
          </div>
          <button className="ghost-button" onClick={props.onSwitchLocal} title="Use the full local library">
            <LogOut size={14} /> Local
          </button>
        </div>
      ) : (
        <p className="profile-mode-note">No profile active: using the full library with universal settings.</p>
      )}

      <div className="profile-tabs">
        <button className={mode === "claim" ? "active" : ""} onClick={() => setMode("claim")}>
          Claim existing
        </button>
        <button className={mode === "create" ? "active" : ""} onClick={() => setMode("create")}>
          Create new
        </button>
      </div>

      <div className="profile-form">
        <input
          placeholder="Profile name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <input
          type="password"
          placeholder="Passphrase"
          value={passphrase}
          onChange={(event) => setPassphrase(event.target.value)}
        />

        {mode === "create" && !props.songPicker ? (
          <small className="profile-hint">
            A new profile starts with an empty library. Import or scan songs once it is active. To
            let new profiles pick songs from this library instead, turn on “Let new profiles pick
            songs” in the settings list.
          </small>
        ) : null}
        {mode === "create" && props.songPicker ? (
          <div className="scope-control">
            <label className="scope-toggle">
              <input type="checkbox" checked={preFill} onChange={(event) => setPreFill(event.target.checked)} />
              Pre-fill from this library
            </label>
            {preFill ? (
              <div className="scope-picker">
                <div className="scope-picker-head">
                  <input
                    placeholder="Search songs…"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                  <span>{chosen.size} selected</span>
                </div>
                <div className="scope-list">
                  {filtered.slice(0, 300).map((track) => (
                    <label key={track.id} className="scope-row">
                      <input type="checkbox" checked={chosen.has(track.id)} onChange={() => toggle(track.id)} />
                      <span className="scope-title">{track.title}</span>
                      <small>{displayArtist(track)}</small>
                    </label>
                  ))}
                  {filtered.length > 300 ? (
                    <p className="scope-more">Showing the first 300. Search to narrow.</p>
                  ) : null}
                </div>
              </div>
            ) : (
              <small className="profile-hint">
                Unticked: the profile starts with an empty library and imports its own songs.
              </small>
            )}
          </div>
        ) : null}

        {error ? <p className="profile-error">{error}</p> : null}

        <button className="primary" disabled={busy} onClick={() => void submit()}>
          {busy ? "Working…" : mode === "claim" ? "Claim profile" : "Create profile"}
        </button>
        {mode === "create" ? (
          <small className="profile-hint">A new profile starts from a copy of the current settings.</small>
        ) : null}
      </div>
    </div>
  );
}

function SettingControlRow(props: {
  control: SettingControl;
  value: number | boolean;
  onChange: (value: number | boolean) => void;
}) {
  const { control } = props;
  const numberValue = typeof props.value === "number" ? props.value : Number(control.default);
  return (
    <div className="setting-control">
      <div className="setting-copy">
        <h3>{control.label}</h3>
        <p>{control.description}</p>
      </div>
      {control.control === "switch" ? (
        <button
          className={props.value ? "switch-control on" : "switch-control"}
          onClick={() => props.onChange(!props.value)}
          role="switch"
          aria-checked={Boolean(props.value)}
          type="button"
        >
          <span className="switch-label">{props.value ? "On" : "Off"}</span>
          <span className="switch-track">
            <span className="switch-knob" />
          </span>
        </button>
      ) : (
        <div className="range-control">
          <input
            type={control.control === "slider" ? "range" : "number"}
            min={control.minimum ?? undefined}
            max={control.maximum ?? undefined}
            step={control.step ?? undefined}
            value={numberValue}
            onChange={(event) => props.onChange(Number(event.target.value))}
          />
          <strong>
            {Number(numberValue).toFixed(control.step && control.step < 1 ? 2 : 0)}
            {control.unit ? ` ${control.unit}` : ""}
          </strong>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildFacets(
  tracks: Track[]
): Record<"source" | "artist" | "theme" | "variant" | "tag", Facet[]> {
  const counters: Record<string, Map<string, number>> = {
    source: new Map(),
    artist: new Map(),
    theme: new Map(),
    variant: new Map(),
    tag: new Map()
  };
  for (const track of tracks) {
    for (const group of track.groups) {
      const bucket = counters[group.group_type as keyof typeof counters] ?? counters.theme;
      bucket.set(group.name, (bucket.get(group.name) ?? 0) + 1);
    }
    if (track.sub_group) {
      counters.variant.set(track.sub_group, (counters.variant.get(track.sub_group) ?? 0) + 1);
    }
    for (const name of track.tags ?? []) {
      counters.tag.set(name, (counters.tag.get(name) ?? 0) + 1);
    }
  }
  const toFacets = (type: string, map: Map<string, number>): Facet[] =>
    [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ key: `${type}::${name}`, label: name, type, count }));
  return {
    source: toFacets("source", counters.source),
    artist: toFacets("artist", counters.artist),
    theme: toFacets("theme", counters.theme),
    variant: toFacets("variant", counters.variant),
    tag: toFacets("tag", counters.tag)
  };
}

function topGroupsByCount(tracks: Track[]): { label: string; value: number }[] {
  const counts = new Map<string, number>();
  for (const track of tracks) {
    for (const group of track.groups) {
      counts.set(group.name, (counts.get(group.name) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([label, value]) => ({ label, value }));
}

function mostPlayedTracks(events: PlaybackEvent[], tracks: Track[]): { label: string; value: number }[] {
  const titleById = new Map(tracks.map((track) => [track.id, track.title]));
  const counts = new Map<number, number>();
  for (const event of events) {
    if (event.event_type === "completed" || event.event_type === "started") {
      counts.set(event.track_id, (counts.get(event.track_id) ?? 0) + (event.event_type === "completed" ? 1 : 0));
    }
  }
  return [...counts.entries()]
    .filter(([, value]) => value > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([id, value]) => ({ label: titleById.get(id) ?? `Track ${id}`, value }));
}

function listeningHealth(events: PlaybackEvent[]) {
  // Use terminal events (completed/skipped) so listen time isn't double-counted.
  const terminal = events.filter((e) => e.event_type === "completed" || e.event_type === "skipped");
  const loud = terminal.filter((e) => e.avg_level != null);
  const avg = loud.length ? loud.reduce((sum, e) => sum + (e.avg_level ?? 0), 0) / loud.length : 0;
  const peak = terminal.reduce((max, e) => Math.max(max, e.peak_level ?? 0), 0);
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  let weekSeconds = 0;
  let doseSeconds = 0;
  for (const e of terminal) {
    const at = Date.parse(e.created_at);
    if (!Number.isFinite(at) || at < weekAgo) {
      continue;
    }
    const secs = Math.max(0, Math.min(e.progress_seconds ?? 0, e.duration_seconds ?? (e.progress_seconds ?? 0)));
    weekSeconds += secs;
    doseSeconds += (e.avg_level ?? 0) * secs;
  }
  // Rough relative allowance: 40 h at level 0.5 ≈ a full week. Not calibrated dB.
  const dosePct = Math.round((doseSeconds / (0.5 * 40 * 3600)) * 100);
  return { samples: loud.length, avg, peak, weekSeconds, dosePct };
}

function formatClock(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function isFactorApplicable(factor: RatingFactor, track: Track): boolean {
  if (factor.applies_to_variants_only && !track.sub_group) {
    return false;
  }
  if (track.has_lyrics && !factor.applies_to_lyrics) {
    return false;
  }
  if (!track.has_lyrics && !factor.applies_to_instrumental) {
    return false;
  }
  return true;
}

function parseGroups(value: string, existing: TrackGroup[]): TrackGroup[] {
  const byName = new Map(existing.map((group) => [group.name, group]));
  return value
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((name) => byName.get(name) ?? { id: 0, name, group_type: "theme", share: null });
}

function settingsToDraft(settings: AppSettings): Record<string, number | boolean> {
  return Object.fromEntries(settings.controls.map((control) => [control.key, settings[control.key]])) as Record<
    string,
    number | boolean
  >;
}

function artStyle(seed: number): React.CSSProperties {
  const hue = (seed * 47) % 360;
  const hue2 = (hue + 38) % 360;
  return {
    background: `linear-gradient(135deg, hsl(${hue} 42% 32%), hsl(${hue2} 38% 22%))`
  };
}

function selectedAsset(item: QueueItem | null) {
  if (!item) {
    return null;
  }
  return item.track.assets.find((asset) => asset.id === item.media_asset_id) ?? null;
}

function message(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}
