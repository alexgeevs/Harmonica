import {
  BarChart3,
  ClipboardCheck,
  Clock,
  Download,
  Library as LibraryIcon,
  ListMusic,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings as SettingsIcon,
  SkipBack,
  SkipForward,
  Sparkles,
  Star,
  Trash2,
  Video,
  Volume2,
  VolumeX,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, savedQueuesSupported } from "./api";
import { displayArtist, formatTime, pct, whyReasons } from "./format";
import CurateView from "./CurateView";
import { matchPreset, PRESETS, type Preset } from "./presets";
import { usePlayer, type PlayerApi } from "./usePlayer";
import type {
  AppSettings,
  PlaybackEvent,
  QueueItem,
  RatingFactor,
  RunSummary,
  SettingControl,
  StatsSummary,
  Track,
  TrackGroup,
  WhyReason
} from "./types";

type View = "queue" | "library" | "curate" | "stats" | "settings";

const VIEW_TITLES: Record<View, string> = {
  queue: "Listen",
  library: "Library",
  curate: "Curate",
  stats: "Insights",
  settings: "Settings"
};

export default function App() {
  const player = usePlayer();
  const [view, setView] = useState<View>("queue");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [ratingFactors, setRatingFactors] = useState<RatingFactor[]>([]);
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [events, setEvents] = useState<PlaybackEvent[]>([]);
  const [savedRuns, setSavedRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const videoStageRef = useRef<HTMLDivElement>(null);
  const videoParkRef = useRef<HTMLDivElement>(null);
  const currentIsVideo = selectedAsset(player.currentItem)?.asset_type === "video";

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
  }, [player]);

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
    } catch (err) {
      setError(message(err, "Could not reach the Harmonica backend. Is it running?"));
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

  async function generateQueue(length: number, seed: string) {
    setBusy(true);
    setError(null);
    try {
      const run = await api.generateQueue(length, seed.trim() || undefined);
      player.loadQueue(run, { autoplay: true });
      void refreshSavedRuns();
    } catch (err) {
      setError(message(err, "Could not generate a queue"));
    } finally {
      setBusy(false);
    }
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

  async function saveTrack(track: Track) {
    setBusy(true);
    setError(null);
    try {
      const saved = await api.updateTrack(track);
      setTracks((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      void refreshStats();
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

  return (
    <div className="app-shell">
      <Sidebar view={view} onView={setView} trackCount={tracks.length} />

      <main className="workspace">
        <header className="topbar">
          <h2>{VIEW_TITLES[view]}</h2>
          <div className="topbar-actions">
            {error ? <span className="error-text">{error}</span> : null}
            <button className="icon-button" title="Refresh" onClick={() => void refreshAll()}>
              <RefreshCw size={18} />
            </button>
          </div>
        </header>

        <div className="view-scroll">
          {view === "queue" ? (
            <QueueView
              player={player}
              busy={busy}
              defaultLength={settings?.default_playlist_length ?? 50}
              savedRuns={savedRuns}
              currentIsVideo={currentIsVideo}
              videoStageRef={videoStageRef}
              onGenerate={generateQueue}
              onLoadRun={loadSavedRun}
              onRefreshSaved={refreshSavedRuns}
              onRenameRun={renameRun}
              onDeleteRun={deleteRun}
            />
          ) : null}

          {view === "library" ? (
            <LibraryView
              tracks={tracks}
              ratingFactors={ratingFactors}
              busy={busy}
              onSave={saveTrack}
              onRescan={refreshAll}
            />
          ) : null}

          {view === "curate" ? <CurateView tracks={tracks} onApplied={refreshAll} /> : null}

          {view === "stats" && stats ? <StatsView stats={stats} tracks={tracks} events={events} /> : null}

          {view === "settings" && settings ? (
            <SettingsView settings={settings} ratingFactors={ratingFactors} busy={busy} onSave={saveSettings} />
          ) : null}
        </div>
      </main>

      <PlayerBar player={player} />
      {/* The single <video> element lives here whenever it isn't on the now-playing stage. */}
      <div ref={videoParkRef} className="video-park" aria-hidden />
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
    { key: "curate", label: "Curate", icon: <ClipboardCheck size={18} /> },
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
            {item.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <Sparkles size={14} />
        <span>Tuned to play what you love without wearing it out.</span>
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
  const progress = player.duration > 0 ? player.currentTime / player.duration : 0;

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
          <span>{formatTime(player.currentTime)}</span>
          <Seekbar value={progress} onSeek={(ratio) => player.seek(ratio * (player.duration || 0))} disabled={!item} />
          <span>{formatTime(player.duration)}</span>
        </div>
      </div>

      <div className="player-right">
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
  onGenerate: (length: number, seed: string) => void;
  onLoadRun: (id: number) => void;
  onRefreshSaved: () => void;
  onRenameRun: (id: number, name: string) => void;
  onDeleteRun: (id: number) => void;
}) {
  const { player } = props;
  const [length, setLength] = useState(props.defaultLength);
  const [seed, setSeed] = useState("");
  const item = player.currentItem;

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
        <div className={`now-card ${props.currentIsVideo ? "has-video" : ""}`}>
          {props.currentIsVideo ? (
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
            <span>{item ? displayArtist(item.track) : "Harmonica builds a fresh listening session for you."}</span>
            {item ? <ChipRow groups={item.track.groups} subGroup={item.track.sub_group} /> : null}
          </div>
        </div>

        {item ? <WhyThisSong item={item} /> : null}

        <div className="generate-card">
          <h4>Build a session</h4>
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
            <button className="primary" disabled={props.busy} onClick={() => props.onGenerate(length, seed)}>
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
        <small>Generate a session and it will appear here, ready to reorder, trim, and play.</small>
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
          <span className="tag soon" title="Media still downloading">
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

function WhyThisSong(props: { item: QueueItem }) {
  const reasons = whyReasons(props.item);
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
    </div>
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
    return <p className="saved-empty">Saved sessions will show up here once you generate a few.</p>;
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
  ratingFactors: RatingFactor[];
  busy: boolean;
  onSave: (track: Track) => Promise<Track>;
  onRescan: () => void;
}) {
  const [search, setSearch] = useState("");
  const [facet, setFacet] = useState<string>("all");
  const [selected, setSelected] = useState<Track | null>(null);
  const [scanPath, setScanPath] = useState("");
  const [scanning, setScanning] = useState(false);

  const facets = useMemo(() => buildFacets(props.tracks), [props.tracks]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return props.tracks.filter((track) => {
      if (facet !== "all") {
        const [type, name] = facet.split("::");
        if (type === "variant") {
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
      return [track.title, track.artist, track.album, track.sub_group, ...track.groups.map((g) => g.name)]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(needle));
    });
  }, [props.tracks, search, facet]);

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
        <FacetGroup title="Sources" facets={facets.source} active={facet} onPick={setFacet} />
        <FacetGroup title="Artists" facets={facets.artist} active={facet} onPick={setFacet} />
        <FacetGroup title="Themes" facets={facets.theme} active={facet} onPick={setFacet} />
        <FacetGroup title="Variant families" facets={facets.variant} active={facet} onPick={setFacet} />
      </aside>

      <div className="library-main">
        <div className="library-toolbar">
          <label className="search-box">
            <Search size={16} />
            <input value={search} placeholder="Search title, artist, group…" onChange={(e) => setSearch(e.target.value)} />
          </label>
          <div className="scan-box">
            <input value={scanPath} placeholder="Scan a folder…" onChange={(e) => setScanPath(e.target.value)} />
            <button className="primary" disabled={scanning} onClick={() => void scan()}>
              <Plus size={16} /> Scan
            </button>
          </div>
        </div>

        <div className="track-list">
          {filtered.length === 0 ? (
            <div className="track-empty">No tracks match this view.</div>
          ) : (
            filtered.map((track) => (
              <button
                key={track.id}
                className={`track-card ${selected?.id === track.id ? "active" : ""}`}
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
          factors={props.ratingFactors}
          busy={props.busy}
          onSave={async (draft) => setSelected(await props.onSave(draft))}
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

function FacetGroup(props: { title: string; facets: Facet[]; active: string; onPick: (key: string) => void }) {
  if (props.facets.length === 0) {
    return null;
  }
  return (
    <div className="facet-group">
      <h5>{props.title}</h5>
      {props.facets.map((entry) => (
        <button
          key={entry.key}
          className={props.active === entry.key ? "facet active" : "facet"}
          onClick={() => props.onPick(entry.key)}
        >
          {entry.label} <b>{entry.count}</b>
        </button>
      ))}
    </div>
  );
}

function MiniRating(props: { value: number | null }) {
  if (props.value == null) {
    return <span className="mini-rating unrated">Unrated</span>;
  }
  return (
    <span className="mini-rating" title={`Overall ${props.value}/5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} size={12} fill={n <= props.value! ? "currentColor" : "none"} />
      ))}
    </span>
  );
}

function TrackEditor(props: {
  track: Track;
  factors: RatingFactor[];
  busy: boolean;
  onSave: (track: Track) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<Track>(props.track);
  useEffect(() => setDraft(props.track), [props.track]);

  function update<K extends keyof Track>(key: K, value: Track[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

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
        <button className="icon-button ghost" title="Close" onClick={props.onClose}>
          <X size={18} />
        </button>
      </div>

      <div className="editor-section">
        <h5>Ratings</h5>
        <div className="rating-grid">
          {applicable.map((factor) => (
            <StarRating
              key={factor.key}
              label={factor.label}
              value={draft.ratings[factor.key] ?? null}
              onChange={(value) =>
                setDraft((current) => ({ ...current, ratings: { ...current.ratings, [factor.key]: value } }))
              }
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

      <button className="primary save-button" disabled={props.busy} onClick={() => props.onSave(draft)}>
        <Save size={16} /> Save changes
      </button>
    </aside>
  );
}

function StarRating(props: { label: string; value: number | null; onChange: (value: number | null) => void }) {
  return (
    <div className="star-rating">
      <span>{props.label}</span>
      <div>
        {[1, 2, 3, 4, 5].map((value) => (
          <button
            key={value}
            className={props.value != null && value <= props.value ? "active" : ""}
            title={`${props.label}: ${value}`}
            onClick={() => props.onChange(props.value === value ? null : value)}
          >
            <Star size={15} fill={props.value != null && value <= props.value ? "currentColor" : "none"} />
          </button>
        ))}
        <button className="clear" title="Clear" onClick={() => props.onChange(null)}>
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

  return (
    <section className="stats-view">
      <div className="stat-cards">
        <StatCard label="Library" value={stats.track_count} hint="tracks" />
        <StatCard label="Coverage" value={`${pct(stats.rated_track_count, stats.track_count)}%`} hint={`${stats.rated_track_count} rated`} />
        <StatCard label="Heard at least once" value={`${pct(playedIds.size, stats.track_count)}%`} hint={`${playedIds.size} tracks`} />
        <StatCard label="Visual tracks" value={stats.video_track_count} hint="with video" />
        <StatCard label="Groups" value={stats.group_count} hint="weight groups" />
        <StatCard label="Completion rate" value={`${completionRate}%`} hint={`${stats.completed_count} finished`} />
      </div>

      <div className="stat-panels">
        <div className="stat-panel">
          <h4>Listening coverage</h4>
          <CoverageBar label="Rated" value={stats.rated_track_count} total={stats.track_count} tone="boost" />
          <CoverageBar label="Heard" value={playedIds.size} total={stats.track_count} tone="neutral" />
          <CoverageBar label="Still unrated" value={stats.unrated_track_count} total={stats.track_count} tone="suppress" />
          <p className="stat-note">
            Cold-start keeps surfacing unrated tracks until every song has had a fair chance — coverage should
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
            <p className="stat-note">Nothing played yet — generate a queue and press play.</p>
          ) : (
            <BarList rows={mostPlayed} />
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

const SETTING_SECTIONS: { title: string; note: string; keys: string[] }[] = [
  {
    title: "Recommendation core",
    note: "How strongly groups and your ratings shape the queue.",
    keys: [
      "beta",
      "default_playlist_length",
      "enable_group_rating_multiplier",
      "song_rating_min_multiplier",
      "song_rating_max_multiplier"
    ]
  },
  {
    title: "Anti-repetition & variety",
    note: "How quickly a just-played song, group, or variant is allowed back.",
    keys: ["group_cooldown_floor", "sub_group_cooldown_floor", "group_clustering_bias"]
  },
  {
    title: "History & feedback",
    note: "How your plays and skips steer the next session.",
    keys: ["history_influence_enabled", "skip_penalty_strength"]
  },
  {
    title: "Coverage (cold start)",
    note: "Making sure every song gets a fair first hearing.",
    keys: ["cold_start_enabled", "cold_start_unrated_boost"]
  },
  {
    title: "Visuals",
    note: "Prioritising tracks with video while you're here to watch.",
    keys: ["visual_priority_enabled", "visual_priority_multiplier"]
  }
];

function SettingsView(props: {
  settings: AppSettings;
  ratingFactors: RatingFactor[];
  busy: boolean;
  onSave: (values: Record<string, number | boolean>) => void;
}) {
  const [draft, setDraft] = useState<Record<string, number | boolean>>(() => settingsToDraft(props.settings));
  useEffect(() => setDraft(settingsToDraft(props.settings)), [props.settings]);

  const dirty = useMemo(
    () => props.settings.controls.some((control) => draft[control.key] !== props.settings[control.key]),
    [draft, props.settings]
  );
  const activePreset = useMemo(() => matchPreset(draft), [draft]);

  const controlsByKey = useMemo(
    () => new Map(props.settings.controls.map((control) => [control.key as string, control])),
    [props.settings.controls]
  );
  const known = new Set(SETTING_SECTIONS.flatMap((section) => section.keys));
  const extraKeys = props.settings.controls.map((c) => c.key as string).filter((key) => !known.has(key));

  function applyPreset(preset: Preset) {
    const next = { ...draft, ...preset.values };
    setDraft(next);
    props.onSave(next);
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

  return (
    <section className="settings-view">
      <div className="settings-main">
        <div className="preset-card">
          <div className="preset-head">
            <h4>Listening presets</h4>
            <p>One tap tunes every control below. You can still fine-tune afterwards.</p>
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
            <p className="preset-active custom">Custom mix — tweak any control, or pick a preset to reset.</p>
          )}
        </div>

        {SETTING_SECTIONS.map((section) => (
          <div key={section.title} className="settings-section">
            <div className="section-head">
              <h4>{section.title}</h4>
              <p>{section.note}</p>
            </div>
            <div className="settings-controls">{renderControls(section.keys)}</div>
          </div>
        ))}

        {extraKeys.length ? (
          <div className="settings-section">
            <div className="section-head">
              <h4>More</h4>
            </div>
            <div className="settings-controls">{renderControls(extraKeys)}</div>
          </div>
        ) : null}
      </div>

      <div className="settings-side">
        <button className="primary save-button" disabled={props.busy || !dirty} onClick={() => props.onSave(draft)}>
          <Save size={16} /> {dirty ? "Save settings" : "Saved"}
        </button>
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
          type="button"
        >
          <span />
          {props.value ? "On" : "Off"}
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

function buildFacets(tracks: Track[]): Record<"source" | "artist" | "theme" | "variant", Facet[]> {
  const counters: Record<string, Map<string, number>> = {
    source: new Map(),
    artist: new Map(),
    theme: new Map(),
    variant: new Map()
  };
  for (const track of tracks) {
    for (const group of track.groups) {
      const bucket = counters[group.group_type as keyof typeof counters] ?? counters.theme;
      bucket.set(group.name, (bucket.get(group.name) ?? 0) + 1);
    }
    if (track.sub_group) {
      counters.variant.set(track.sub_group, (counters.variant.get(track.sub_group) ?? 0) + 1);
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
    variant: toFacets("variant", counters.variant)
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
