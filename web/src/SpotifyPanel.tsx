import { useMemo, useState } from "react";
import { Check, ListMusic, Search } from "lucide-react";
import { api } from "./api";
import { isLikelyInLibrary, libraryTitleSet, type SpotifyPlaylist } from "./spotify";
import type { Track } from "./types";

/**
 * Read a public Spotify playlist and compare it against the local library. This calls the
 * Harmonica backend, which reads Spotify server-side, so the browser never contacts Spotify and
 * the app credentials stay on the server. It shows track names only. No audio is downloaded.
 */
export function SpotifyPanel(props: { libraryTracks: Track[] }) {
  const [url, setUrl] = useState("");
  const [playlist, setPlaylist] = useState<SpotifyPlaylist | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const titles = useMemo(() => libraryTitleSet(props.libraryTracks), [props.libraryTracks]);
  const matched = useMemo(
    () => (playlist ? playlist.tracks.filter((track) => isLikelyInLibrary(track, titles)).length : 0),
    [playlist, titles]
  );

  async function fetchPlaylist() {
    const link = url.trim();
    if (!link) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setPlaylist(await api.spotifyPlaylist(link));
    } catch (err) {
      setPlaylist(null);
      setError(err instanceof Error ? err.message : "Could not read that playlist");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="spotify-panel">
      <div className="spotify-head">
        <div>
          <h4>Compare a Spotify playlist</h4>
          <p>
            Paste a public playlist link to see which of its songs you already have. Track names
            only, read through Spotify's Web API. No audio is downloaded.
          </p>
        </div>
      </div>
      <div className="spotify-input-row">
        <input
          value={url}
          placeholder="https://open.spotify.com/playlist/…"
          onChange={(event) => setUrl(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void fetchPlaylist();
            }
          }}
        />
        <button className="primary" disabled={busy || !url.trim()} onClick={() => void fetchPlaylist()}>
          <Search size={16} /> Read
        </button>
      </div>

      {error ? <div className="curate-banner error">{error}</div> : null}

      {playlist ? (
        <div className="spotify-result">
          <div className="spotify-result-head">
            <ListMusic size={18} />
            <strong>{playlist.name ?? "Playlist"}</strong>
            <span>
              {playlist.tracks.length} track{playlist.tracks.length === 1 ? "" : "s"} · {matched} in
              your library
            </span>
          </div>
          {playlist.truncated ? (
            <small className="spotify-note">Only the first 500 tracks were read.</small>
          ) : null}
          <ul className="spotify-list">
            {playlist.tracks.map((track, index) => {
              const owned = isLikelyInLibrary(track, titles);
              return (
                <li key={`${track.spotify_id ?? index}`} className={owned ? "owned" : ""}>
                  <span className="spotify-track-name">{track.name}</span>
                  <span className="spotify-track-artist">{track.artists.join(", ")}</span>
                  {owned ? (
                    <span className="spotify-owned" title="Likely already in your library">
                      <Check size={13} /> in library
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
