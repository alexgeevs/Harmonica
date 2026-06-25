import { Check, Download, FileUp, Sparkles, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { api } from "./api";
import { diffLibrary, parseProposedLibrary, type LibraryDiff, type TrackDiff } from "./curation";
import type { LibraryExport, Track } from "./types";

/**
 * Curation review workflow. Export the library for an external curation agent,
 * then load its proposed JSON back, see exactly what would change, and accept or
 * reject per track before anything is written.
 */
export default function CurateView(props: { tracks: Track[]; onApplied: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [proposed, setProposed] = useState<LibraryExport | null>(null);
  const [diff, setDiff] = useState<LibraryDiff | null>(null);
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const idBySong = useMemo(() => new Map(props.tracks.map((track) => [track.song_id, track.id])), [props.tracks]);

  async function loadProposed(text: string) {
    setError(null);
    setNote(null);
    try {
      const next = parseProposedLibrary(text);
      const current = await api.exportLibrary();
      const computed = diffLibrary(current, next);
      setProposed(next);
      setDiff(computed);
      setAccepted(new Set(computed.tracks.map((entry) => entry.song_id)));
      if (computed.tracks.length === 0) {
        setNote("No differences found — your library already matches this file.");
      }
    } catch (err) {
      setProposed(null);
      setDiff(null);
      setError(err instanceof Error ? err.message : "Could not read that file");
    }
  }

  function onFile(file: File | undefined) {
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => void loadProposed(String(reader.result ?? ""));
    reader.readAsText(file);
  }

  async function downloadCurrent() {
    setBusy(true);
    try {
      const current = await api.exportLibrary();
      const blob = new Blob([JSON.stringify(current, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "harmonica-library.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  function toggle(songId: string) {
    setAccepted((current) => {
      const next = new Set(current);
      if (next.has(songId)) {
        next.delete(songId);
      } else {
        next.add(songId);
      }
      return next;
    });
  }

  async function applyAccepted() {
    if (!diff) {
      return;
    }
    setBusy(true);
    setError(null);
    setNote(null);
    const chosen = diff.tracks.filter((entry) => accepted.has(entry.song_id));
    const newTracks = chosen.filter((entry) => entry.status === "new").map((entry) => entry.proposed);
    const edits = chosen.filter((entry) => entry.status === "modified");
    try {
      for (const entry of edits) {
        const id = idBySong.get(entry.song_id);
        if (id == null) {
          continue;
        }
        const p = entry.proposed;
        await api.updateTrackFields(id, {
          title: p.title,
          artist: p.artist ?? null,
          album: p.album ?? null,
          has_lyrics: p.has_lyrics,
          sub_group: p.sub_group ?? null,
          manual_multiplier: p.manual_multiplier ?? 1.0,
          groups: (p.groups ?? []).map((group) => ({
            name: group.name,
            group_type: group.group_type,
            share: group.share ?? null
          })),
          cooldown_tags: p.cooldown_tags ?? [],
          ratings: p.ratings ?? {}
        });
      }
      if (newTracks.length) {
        await api.importLibrary({ tracks: newTracks });
      }
      setNote(`Applied ${chosen.length} change${chosen.length === 1 ? "" : "s"}.`);
      setProposed(null);
      setDiff(null);
      setAccepted(new Set());
      props.onApplied();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Apply failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="curate-view">
      <div className="curate-intro">
        <div>
          <h3>Curation review</h3>
          <p>
            Hand your library to a curation agent, then bring its proposal back here. You'll see every
            change and approve them one by one — nothing is written until you apply.
          </p>
        </div>
        <div className="curate-actions">
          <button className="primary ghost-primary" disabled={busy} onClick={() => void downloadCurrent()}>
            <Download size={16} /> Export library
          </button>
          <button className="primary" disabled={busy} onClick={() => fileRef.current?.click()}>
            <FileUp size={16} /> Load proposal
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(event) => onFile(event.target.files?.[0])}
          />
        </div>
      </div>

      {error ? <div className="curate-banner error">{error}</div> : null}
      {note ? <div className="curate-banner ok">{note}</div> : null}

      {!diff ? (
        <PasteArea onSubmit={loadProposed} busy={busy} />
      ) : (
        <DiffReview
          diff={diff}
          accepted={accepted}
          busy={busy}
          onToggle={toggle}
          onAll={() => setAccepted(new Set(diff.tracks.map((entry) => entry.song_id)))}
          onNone={() => setAccepted(new Set())}
          onApply={() => void applyAccepted()}
          onCancel={() => {
            setDiff(null);
            setProposed(null);
          }}
        />
      )}
      {proposed ? null : null}
    </section>
  );
}

function PasteArea(props: { onSubmit: (text: string) => void; busy: boolean }) {
  const [text, setText] = useState("");
  return (
    <div className="paste-area">
      <label>
        …or paste the proposed library JSON
        <textarea
          value={text}
          placeholder='{ "tracks": [ … ] }'
          onChange={(event) => setText(event.target.value)}
          rows={8}
        />
      </label>
      <button className="primary" disabled={props.busy || !text.trim()} onClick={() => props.onSubmit(text)}>
        Review changes
      </button>
    </div>
  );
}

function DiffReview(props: {
  diff: LibraryDiff;
  accepted: Set<string>;
  busy: boolean;
  onToggle: (songId: string) => void;
  onAll: () => void;
  onNone: () => void;
  onApply: () => void;
  onCancel: () => void;
}) {
  const { diff } = props;
  return (
    <div className="diff-review">
      <div className="diff-summary">
        <div>
          <strong>{diff.tracks.length}</strong> changed ·{" "}
          <strong>{diff.tracks.filter((t) => t.status === "new").length}</strong> new ·{" "}
          <strong>{diff.unchanged}</strong> unchanged
          {diff.missingFromProposed ? <> · {diff.missingFromProposed} not in proposal</> : null}
        </div>
        <div className="diff-controls">
          <button className="link" onClick={props.onAll}>
            Accept all
          </button>
          <button className="link" onClick={props.onNone}>
            Clear
          </button>
          <button className="ghost-btn" onClick={props.onCancel}>
            Cancel
          </button>
          <button className="primary" disabled={props.busy || props.accepted.size === 0} onClick={props.onApply}>
            <Check size={16} /> Apply {props.accepted.size}
          </button>
        </div>
      </div>

      {diff.tracks.length === 0 ? (
        <div className="diff-empty">
          <Sparkles size={26} />
          <p>Nothing to review — the proposal matches your library.</p>
        </div>
      ) : (
        <ul className="diff-list">
          {diff.tracks.map((entry) => (
            <DiffRow
              key={entry.song_id}
              entry={entry}
              checked={props.accepted.has(entry.song_id)}
              onToggle={() => props.onToggle(entry.song_id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function DiffRow(props: { entry: TrackDiff; checked: boolean; onToggle: () => void }) {
  const { entry } = props;
  return (
    <li className={`diff-row ${props.checked ? "accepted" : "rejected"}`}>
      <button className={`diff-check ${props.checked ? "on" : ""}`} onClick={props.onToggle} title="Accept this change">
        {props.checked ? <Check size={14} /> : <X size={14} />}
      </button>
      <div className="diff-body">
        <div className="diff-title">
          <strong>{entry.title}</strong>
          <span className={`diff-badge ${entry.status}`}>{entry.status}</span>
        </div>
        <div className="diff-changes">
          {entry.fieldChanges.map((change) => (
            <span key={change.field} className="diff-change">
              <em>{change.field}</em>
              <s>{display(change.before)}</s>
              <b>{display(change.after)}</b>
            </span>
          ))}
          {entry.groupsAdded.map((name) => (
            <span key={`add-${name}`} className="diff-change add">
              + group <b>{name}</b>
            </span>
          ))}
          {entry.groupsRemoved.map((name) => (
            <span key={`rem-${name}`} className="diff-change remove">
              − group <s>{name}</s>
            </span>
          ))}
          {entry.ratingChanges.map((change) => (
            <span key={`rating-${change.key}`} className="diff-change">
              <em>{change.key}</em>
              <s>{change.before ?? "—"}</s>
              <b>{change.after ?? "—"}</b>
            </span>
          ))}
        </div>
      </div>
    </li>
  );
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "yes" : "no";
  }
  return String(value);
}
