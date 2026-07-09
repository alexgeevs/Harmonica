import { AlertTriangle, Check, KeyRound, ListVideo, Youtube } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import type { LibraryExport } from "./types";
import {
  applyClusters,
  factorNeedsKey,
  IMPORT_FACTORS,
  type YouTubeImportPreview
} from "./youtube-import";

/**
 * Paste a list of YouTube links, pick which factors to organise by, and get proposed tracks back.
 * The daemon reads each video's metadata server-side, so the browser never contacts YouTube here.
 * Nothing is written: the proposal is handed up to the review screen, where the user approves it.
 */
export function YouTubeImportPanel(props: { onProposal: (library: LibraryExport) => void }) {
  const [factors, setFactors] = useState<Set<string>>(new Set(["channel", "title"]));
  const [links, setLinks] = useState("");
  const [preview, setPreview] = useState<YouTubeImportPreview | null>(null);
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .youtubeConfig()
      .then((config) => setHasApiKey(config.has_api_key))
      .catch(() => setHasApiKey(false));
  }, []);

  const needsKey = factorNeedsKey(factors);
  const keyMissing = needsKey && hasApiKey === false;

  function toggleFactor(key: string) {
    setFactors((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function toggleCluster(key: string) {
    setConfirmed((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  async function runPreview() {
    if (!links.trim() || keyMissing) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.youtubeImportPreview(links, [...factors]);
      setPreview(result);
      setConfirmed(new Set()); // clusters are opt-in: the user ticks the ones to group
    } catch (err) {
      setPreview(null);
      setError(err instanceof Error ? err.message : "Could not read those links");
    } finally {
      setBusy(false);
    }
  }

  function review() {
    if (!preview) {
      return;
    }
    props.onProposal(applyClusters(preview.tracks, preview.clusters, confirmed));
  }

  const unreadable = preview ? preview.videos.filter((video) => !video.available).length : 0;

  return (
    <div className="yti-panel">
      <div className="yti-head">
        <Youtube size={18} />
        <div>
          <h4>Import from a list of YouTube links</h4>
          <p>
            Paste video links (one per line, or separated by spaces). Harmonica reads their
            metadata on the server and organises them into tracks for you to review. The video
            plays later through YouTube's official player. Nothing is downloaded.
          </p>
        </div>
      </div>

      <fieldset className="yti-factors">
        <legend>Organise by</legend>
        {IMPORT_FACTORS.map((factor) => (
          <label key={factor.key} className={factor.needsKey ? "needs-key" : ""}>
            <input
              type="checkbox"
              checked={factors.has(factor.key)}
              onChange={() => toggleFactor(factor.key)}
            />
            <span className="yti-factor-label">
              {factor.label}
              {factor.needsKey ? <em className="yti-key-tag">key</em> : null}
            </span>
            <small>{factor.hint}</small>
          </label>
        ))}
      </fieldset>

      {needsKey && hasApiKey ? (
        <p className="yti-key-note ok">
          <Check size={14} /> Using your Data API key for the factors marked “key”.
        </p>
      ) : null}

      {keyMissing ? (
        <div className="yti-key-help">
          <div className="yti-key-help-head">
            <KeyRound size={15} /> Those factors need a YouTube Data API key
          </div>
          <p>
            The factors marked “key” read extra detail through YouTube's Data API, which needs your
            own key. The keyless factors (uploader and title) work without one.
          </p>
          <ol>
            <li>
              Create a free key in the Google Cloud console. Enable “YouTube Data API v3”, then make
              an API key.
            </li>
            <li>
              Give it to the server. Either set the environment variable{" "}
              <code>HARMONICA_YOUTUBE_DATA_API_KEY</code> before you start it, or put the key in a
              file named <code>youtube_data_api.key</code> inside the Harmonica home folder
              (<code>.harmonica</code> by default). Reload afterwards.
            </li>
          </ol>
          <p className="yti-key-help-foot">
            Until then, leave the “key” factors unticked to import with the uploader and title only.
          </p>
        </div>
      ) : null}

      <textarea
        className="yti-links"
        value={links}
        rows={5}
        placeholder={"https://www.youtube.com/watch?v=…\nhttps://youtu.be/…"}
        onChange={(event) => setLinks(event.target.value)}
      />

      {error ? <div className="curate-banner error">{error}</div> : null}

      <div className="yti-actions">
        <button
          className="primary"
          disabled={busy || !links.trim() || keyMissing}
          onClick={() => void runPreview()}
        >
          <ListVideo size={16} /> Read and organise
        </button>
      </div>

      {preview ? (
        <div className="yti-result">
          <div className="yti-result-head">
            <strong>{preview.tracks.length}</strong> track
            {preview.tracks.length === 1 ? "" : "s"} organised from {preview.requested} link
            {preview.requested === 1 ? "" : "s"}
            {unreadable ? <> · {unreadable} could not be read</> : null}
            {preview.used_api ? <> · read with your Data API key</> : null}
          </div>
          {preview.truncated ? (
            <small className="yti-note">
              Only the first batch was read. Import these, then paste the rest.
            </small>
          ) : null}

          {preview.clusters.length ? (
            <div className="yti-clusters">
              <div className="yti-clusters-head">
                <AlertTriangle size={14} /> These look like the same song. Tick any you want grouped
                as one version family, after checking them.
              </div>
              {preview.clusters.map((cluster) => (
                <label key={cluster.key} className="yti-cluster">
                  <input
                    type="checkbox"
                    checked={confirmed.has(cluster.key)}
                    onChange={() => toggleCluster(cluster.key)}
                  />
                  <span className="yti-cluster-name">{cluster.suggested_sub_group}</span>
                  <small>
                    {cluster.song_ids.length} videos · {cluster.reason}
                  </small>
                </label>
              ))}
            </div>
          ) : null}

          <ul className="yti-videos">
            {preview.videos.map((video) => (
              <li key={video.video_id} className={video.available ? "" : "unavailable"}>
                <span className="yti-video-title">
                  {video.available ? video.title : "Could not read this video"}
                </span>
                {video.channel ? <span className="yti-video-channel">{video.channel}</span> : null}
                {video.duration_seconds != null ? (
                  <span className="yti-video-dur">{formatDuration(video.duration_seconds)}</span>
                ) : null}
                {video.available && !video.likely_song ? (
                  <span className="yti-flag" title="May not be a song">
                    check
                  </span>
                ) : null}
              </li>
            ))}
          </ul>

          <div className="yti-actions">
            <button className="primary" disabled={!preview.tracks.length} onClick={review}>
              <Check size={16} /> Review {preview.tracks.length} track
              {preview.tracks.length === 1 ? "" : "s"} before importing
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins >= 60) {
    const hours = Math.floor(mins / 60);
    return `${hours}:${String(mins % 60).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${mins}:${String(secs).padStart(2, "0")}`;
}
