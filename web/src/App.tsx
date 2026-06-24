import {
  Download,
  Library,
  Pause,
  Play,
  RefreshCw,
  Save,
  Search,
  Settings,
  SkipForward,
  SlidersHorizontal,
  Star,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { AppSettings, QueueItem, QueueRun, RatingFactor, Track, TrackGroup } from "./types";

type View = "dashboard" | "library" | "settings";

const emptyQueue: QueueRun = { id: 0, length: 0, items: [] };

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [ratingFactors, setRatingFactors] = useState<RatingFactor[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [queue, setQueue] = useState<QueueRun>(emptyQueue);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [playlistLength, setPlaylistLength] = useState(100);
  const [seed, setSeed] = useState("");
  const [scanPath, setScanPath] = useState("");
  const [search, setSearch] = useState("");
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);

  const currentItem = queue.items[currentIndex] ?? null;

  useEffect(() => {
    void refreshAll();
  }, []);

  async function refreshAll() {
    setError(null);
    const [nextSettings, nextFactors, nextTracks] = await Promise.all([
      api.settings(),
      api.ratingFactors(),
      api.tracks()
    ]);
    setSettings(nextSettings);
    setRatingFactors(nextFactors);
    setTracks(nextTracks);
    setPlaylistLength(nextSettings.default_playlist_length);
  }

  async function generateQueue() {
    setBusy(true);
    setError(null);
    try {
      const nextQueue = await api.generateQueue(playlistLength, seed.trim() || undefined);
      setQueue(nextQueue);
      setCurrentIndex(0);
      setPlaying(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate queue");
    } finally {
      setBusy(false);
    }
  }

  async function scanLibrary() {
    if (!scanPath.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.scan(scanPath.trim());
      const nextTracks = await api.tracks();
      setTracks(nextTracks);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveTrack(track: Track) {
    setBusy(true);
    setError(null);
    try {
      const saved = await api.updateTrack(track);
      setTracks((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      setSelectedTrack(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  function skip() {
    setCurrentIndex((index) => Math.min(index + 1, Math.max(queue.items.length - 1, 0)));
    setPlaying(true);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">H</div>
          <div>
            <h1>Harmonica</h1>
            <p>{tracks.length} tracks</p>
          </div>
        </div>
        <nav className="nav-buttons">
          <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>
            <Play size={18} />
            Queue
          </button>
          <button className={view === "library" ? "active" : ""} onClick={() => setView("library")}>
            <Library size={18} />
            Library
          </button>
          <button className={view === "settings" ? "active" : ""} onClick={() => setView("settings")}>
            <Settings size={18} />
            Settings
          </button>
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h2>{view === "dashboard" ? "Queue" : view === "library" ? "Library" : "Settings"}</h2>
            {error ? <p className="error-text">{error}</p> : null}
          </div>
          <button className="icon-button" title="Refresh" onClick={() => void refreshAll()}>
            <RefreshCw size={18} />
          </button>
        </header>

        {view === "dashboard" ? (
          <Dashboard
            currentItem={currentItem}
            queue={queue}
            currentIndex={currentIndex}
            playlistLength={playlistLength}
            seed={seed}
            busy={busy}
            playing={playing}
            onLengthChange={setPlaylistLength}
            onSeedChange={setSeed}
            onGenerate={() => void generateQueue()}
            onSelectIndex={(index) => setCurrentIndex(index)}
            onPlayingChange={setPlaying}
            onSkip={skip}
          />
        ) : null}

        {view === "library" ? (
          <LibraryView
            tracks={tracks}
            scanPath={scanPath}
            search={search}
            selectedTrack={selectedTrack}
            ratingFactors={ratingFactors}
            busy={busy}
            onScanPathChange={setScanPath}
            onSearchChange={setSearch}
            onScan={() => void scanLibrary()}
            onSelectTrack={setSelectedTrack}
            onSave={(track) => void saveTrack(track)}
            onCloseEditor={() => setSelectedTrack(null)}
          />
        ) : null}

        {view === "settings" && settings ? (
          <SettingsView settings={settings} ratingFactors={ratingFactors} />
        ) : null}
      </main>
    </div>
  );
}

function Dashboard(props: {
  currentItem: QueueItem | null;
  queue: QueueRun;
  currentIndex: number;
  playlistLength: number;
  seed: string;
  busy: boolean;
  playing: boolean;
  onLengthChange: (value: number) => void;
  onSeedChange: (value: string) => void;
  onGenerate: () => void;
  onSelectIndex: (index: number) => void;
  onPlayingChange: (playing: boolean) => void;
  onSkip: () => void;
}) {
  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const asset = props.currentItem?.track.assets.find(
    (candidate) => candidate.id === props.currentItem?.media_asset_id
  );
  const mediaUrl = props.currentItem?.media_url ?? null;
  const isVideo = asset?.asset_type === "video";

  function togglePlayback() {
    const media = mediaRef.current;
    if (!media) {
      return;
    }
    if (props.playing) {
      media.pause();
      return;
    }
    void media.play();
  }

  return (
    <section className="dashboard-grid">
      <div className="player-surface">
        <div className="now-playing">
          <p>{props.currentItem ? `#${props.currentIndex + 1}` : "No queue"}</p>
          <h3>{props.currentItem?.track.title ?? "Generate a queue"}</h3>
          <span>{displayArtist(props.currentItem?.track)}</span>
        </div>
        <div className="media-frame">
          {mediaUrl && isVideo ? (
            <video
              ref={(node) => {
                mediaRef.current = node;
              }}
              key={mediaUrl}
              controls
              autoPlay={props.playing}
              src={mediaUrl}
              onPlay={() => props.onPlayingChange(true)}
              onPause={() => props.onPlayingChange(false)}
              onEnded={props.onSkip}
            />
          ) : mediaUrl ? (
            <audio
              ref={(node) => {
                mediaRef.current = node;
              }}
              key={mediaUrl}
              controls
              autoPlay={props.playing}
              src={mediaUrl}
              onPlay={() => props.onPlayingChange(true)}
              onPause={() => props.onPlayingChange(false)}
              onEnded={props.onSkip}
            />
          ) : (
            <div className="empty-player">
              <Play size={42} />
            </div>
          )}
        </div>
        <div className="transport">
          <button
            className="icon-button"
            title={props.playing ? "Pause" : "Play"}
            onClick={togglePlayback}
          >
            {props.playing ? <Pause size={20} /> : <Play size={20} />}
          </button>
          <button className="icon-button" title="Skip" onClick={props.onSkip}>
            <SkipForward size={20} />
          </button>
          {props.queue.id ? (
            <a className="icon-button" title="Export .m3u8" href={`/playlist-runs/${props.queue.id}/m3u8`}>
              <Download size={20} />
            </a>
          ) : null}
        </div>
      </div>

      <div className="queue-panel">
        <div className="queue-controls">
          <label>
            Length
            <input
              type="number"
              min={1}
              max={1000}
              value={props.playlistLength}
              onChange={(event) => props.onLengthChange(Number(event.target.value))}
            />
          </label>
          <label>
            Seed
            <input value={props.seed} onChange={(event) => props.onSeedChange(event.target.value)} />
          </label>
          <button className="primary" onClick={props.onGenerate} disabled={props.busy}>
            <RefreshCw size={18} />
            Generate
          </button>
        </div>
        <ol className="queue-list">
          {props.queue.items.map((item, index) => (
            <li
              key={`${item.position}-${item.track.id}`}
              className={index === props.currentIndex ? "selected" : ""}
            >
              <button onClick={() => props.onSelectIndex(index)}>
                <span>{item.track.title}</span>
                <small>{displayArtist(item.track)}</small>
                <b>{item.score.toFixed(4)}</b>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function LibraryView(props: {
  tracks: Track[];
  scanPath: string;
  search: string;
  selectedTrack: Track | null;
  ratingFactors: RatingFactor[];
  busy: boolean;
  onScanPathChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onScan: () => void;
  onSelectTrack: (track: Track) => void;
  onSave: (track: Track) => void;
  onCloseEditor: () => void;
}) {
  const filtered = useMemo(() => {
    const needle = props.search.trim().toLowerCase();
    if (!needle) {
      return props.tracks;
    }
    return props.tracks.filter((track) =>
      [track.title, track.artist, track.album, track.song_id]
        .filter(Boolean)
        .some((value) => value?.toLowerCase().includes(needle))
    );
  }, [props.search, props.tracks]);

  return (
    <section className="library-layout">
      <div className="library-list">
        <div className="toolbar">
          <label className="scan-input">
            <span>Folder</span>
            <input
              value={props.scanPath}
              onChange={(event) => props.onScanPathChange(event.target.value)}
              placeholder="/Music"
            />
          </label>
          <button className="primary" disabled={props.busy} onClick={props.onScan}>
            <RefreshCw size={18} />
            Scan
          </button>
          <label className="search-box">
            <Search size={18} />
            <input
              value={props.search}
              onChange={(event) => props.onSearchChange(event.target.value)}
              placeholder="Search"
            />
          </label>
        </div>

        <div className="track-table" role="table">
          <div className="track-row header" role="row">
            <span>Title</span>
            <span>Artist</span>
            <span>Groups</span>
            <span>Assets</span>
          </div>
          {filtered.map((track) => (
            <button
              className="track-row"
              role="row"
              key={track.id}
              onClick={() => props.onSelectTrack(track)}
            >
              <span>{track.title}</span>
              <span>{track.artist ?? ""}</span>
              <span>{track.groups.map((group) => group.name).join(", ")}</span>
              <span>{track.assets.length}</span>
            </button>
          ))}
        </div>
      </div>

      {props.selectedTrack ? (
        <TrackEditor
          track={props.selectedTrack}
          factors={props.ratingFactors}
          onSave={props.onSave}
          onClose={props.onCloseEditor}
        />
      ) : (
        <div className="editor-empty">
          <SlidersHorizontal size={34} />
        </div>
      )}
    </section>
  );
}

function TrackEditor(props: {
  track: Track;
  factors: RatingFactor[];
  onSave: (track: Track) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<Track>(props.track);

  useEffect(() => {
    setDraft(props.track);
  }, [props.track]);

  function update<K extends keyof Track>(key: K, value: Track[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function updateGroups(value: string) {
    const groups: TrackGroup[] = value
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((name) => ({ id: 0, name, group_type: "other", share: null }));
    update("groups", groups);
  }

  function updateTags(value: string) {
    update(
      "cooldown_tags",
      value
        .split(";")
        .map((part) => part.trim())
        .filter(Boolean)
    );
  }

  return (
    <aside className="track-editor">
      <div className="editor-header">
        <h3>{draft.title}</h3>
        <button className="icon-button" title="Close" onClick={props.onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="editor-grid">
        <label>
          Title
          <input value={draft.title} onChange={(event) => update("title", event.target.value)} />
        </label>
        <label>
          Artist
          <input value={draft.artist ?? ""} onChange={(event) => update("artist", event.target.value)} />
        </label>
        <label>
          Album
          <input value={draft.album ?? ""} onChange={(event) => update("album", event.target.value)} />
        </label>
        <label>
          Subgroup
          <input
            value={draft.sub_group ?? ""}
            onChange={(event) => update("sub_group", event.target.value || null)}
          />
        </label>
        <label>
          Multiplier
          <input
            type="number"
            step="0.05"
            value={draft.manual_multiplier}
            onChange={(event) => update("manual_multiplier", Number(event.target.value))}
          />
        </label>
        <label className="check-line">
          <input
            type="checkbox"
            checked={draft.has_lyrics}
            onChange={(event) => update("has_lyrics", event.target.checked)}
          />
          Lyrics
        </label>
        <label className="wide">
          Groups
          <input
            value={draft.groups.map((group) => group.name).join("; ")}
            onChange={(event) => updateGroups(event.target.value)}
          />
        </label>
        <label className="wide">
          Cooldown tags
          <input
            value={draft.cooldown_tags.join("; ")}
            onChange={(event) => updateTags(event.target.value)}
          />
        </label>
      </div>

      <div className="rating-grid">
        {props.factors.map((factor) => (
          <StarRating
            key={factor.key}
            label={factor.label}
            value={draft.ratings[factor.key] ?? null}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                ratings: { ...current.ratings, [factor.key]: value }
              }))
            }
          />
        ))}
      </div>

      <div className="asset-list">
        {draft.assets.map((asset) => (
          <div key={asset.id}>
            <span>{asset.asset_type}</span>
            <small>{asset.container ?? asset.codec ?? "file"}</small>
            <code>{asset.file_path}</code>
          </div>
        ))}
      </div>

      <button className="primary save-button" onClick={() => props.onSave(draft)}>
        <Save size={18} />
        Save
      </button>
    </aside>
  );
}

function StarRating(props: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  return (
    <div className="star-rating">
      <span>{props.label}</span>
      <div>
        {[0, 1, 2, 3, 4, 5].map((value) => (
          <button
            key={value}
            className={props.value === value ? "active" : ""}
            title={`${props.label}: ${value}`}
            onClick={() => props.onChange(props.value === value ? null : value)}
          >
            {value === 0 ? <X size={14} /> : <Star size={14} fill="currentColor" />}
          </button>
        ))}
      </div>
    </div>
  );
}

function SettingsView(props: { settings: AppSettings; ratingFactors: RatingFactor[] }) {
  return (
    <section className="settings-layout">
      <dl>
        <div>
          <dt>Home</dt>
          <dd>{props.settings.home}</dd>
        </div>
        <div>
          <dt>Beta</dt>
          <dd>{props.settings.beta}</dd>
        </div>
        <div>
          <dt>Group cooldown floor</dt>
          <dd>{props.settings.group_cooldown_floor}</dd>
        </div>
        <div>
          <dt>Subgroup cooldown floor</dt>
          <dd>{props.settings.sub_group_cooldown_floor}</dd>
        </div>
        <div>
          <dt>Song rating range</dt>
          <dd>
            {props.settings.song_rating_min_multiplier}x to{" "}
            {props.settings.song_rating_max_multiplier}x
          </dd>
        </div>
        <div>
          <dt>Group rating scaffolding</dt>
          <dd>{props.settings.enable_group_rating_multiplier ? "Enabled" : "Stored only"}</dd>
        </div>
      </dl>
      <div className="factor-list">
        {props.ratingFactors.map((factor) => (
          <div key={factor.key}>
            <span>{factor.label}</span>
            <small>{factor.weight.toFixed(2)}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function displayArtist(track?: Track | null) {
  if (!track) {
    return "";
  }
  return [track.artist, track.album].filter(Boolean).join(" · ");
}
