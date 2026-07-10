"use strict";

/* Harmonica demo. Plain JS on purpose: no framework, no build step, a handful of static
   files. The queue itself comes from the repo's real algorithm files, run through Pyodide
   in a web worker (worker.js) so booting Python never freezes the page. */

const META_KEY = "harmonica.demo.meta";
const DATA_KEY = "harmonica.demo.data";
const QUEUE_LEN = 12;
const READ_CONCURRENCY = 8;

const $ = (id) => document.getElementById(id);

function blankData() {
  return {
    tracks: [], groups: [], events: [], queue: [], queueIndex: 0, settings: {},
    ytConsent: false, nextTrackId: 1, nextGroupId: 1,
  };
}

/* ---------------------------------------------------------------- storage
   The cookie prompt is real: the user picks where the demo's data lives and
   for how long. "none" keeps everything in memory and forgets it on leave. */

let mode = null; // null = not asked yet | "none" | "session" | "days" | "local"
let modeDays = 30; // retention for "days" mode, one of DAY_STOPS
let data = blankData();

const DAY_STOPS = [1, 3, 7, 14, 30, 60, 90, 180, 365];

function isLocalMode(m) {
  return m === "local" || m === "days" || m === "local30"; // local30 = pre-slider stored choice
}

function initStorage() {
  try {
    const localMeta = JSON.parse(localStorage.getItem(META_KEY) || "null");
    if (localMeta && isLocalMode(localMeta.mode)) {
      if (localMeta.expiresAt && Date.now() > localMeta.expiresAt) {
        localStorage.removeItem(META_KEY);
        localStorage.removeItem(DATA_KEY);
      } else {
        mode = localMeta.mode;
        if (mode === "days" && DAY_STOPS.includes(localMeta.days)) {
          modeDays = localMeta.days;
        }
        data = Object.assign(blankData(), JSON.parse(localStorage.getItem(DATA_KEY) || "{}"));
        return;
      }
    }
    const sessMeta = JSON.parse(sessionStorage.getItem(META_KEY) || "null");
    if (sessMeta && sessMeta.mode === "session") {
      mode = "session";
      data = Object.assign(blankData(), JSON.parse(sessionStorage.getItem(DATA_KEY) || "{}"));
    }
  } catch {
    data = blankData();
  }
}

function persist() {
  try {
    if (mode === "session") {
      sessionStorage.setItem(DATA_KEY, JSON.stringify(data));
    } else if (isLocalMode(mode)) {
      localStorage.setItem(DATA_KEY, JSON.stringify(data));
    }
  } catch {
    /* storage full or blocked: the demo keeps running in memory */
  }
}

function applyStorageChoice(newMode, days) {
  localStorage.removeItem(META_KEY);
  localStorage.removeItem(DATA_KEY);
  sessionStorage.removeItem(META_KEY);
  sessionStorage.removeItem(DATA_KEY);
  mode = newMode;
  if (mode === "days") {
    const keep = DAY_STOPS.includes(days) ? days : 30;
    modeDays = keep;
    localStorage.setItem(META_KEY, JSON.stringify({
      mode, days: keep, expiresAt: Date.now() + keep * 86400000,
    }));
  } else if (mode === "local") {
    localStorage.setItem(META_KEY, JSON.stringify({ mode, expiresAt: null }));
  } else if (mode === "session") {
    sessionStorage.setItem(META_KEY, JSON.stringify({ mode }));
  }
  persist();
}

function sliderDays() {
  return DAY_STOPS[Number($("days-range").value)] || 30;
}

function showStoragePrompt() {
  const modal = $("storage-modal");
  modal.hidden = false;
  return new Promise((resolve) => {
    modal.querySelectorAll("button[data-mode]").forEach((btn) => {
      btn.onclick = () => {
        modal.hidden = true;
        applyStorageChoice(btn.dataset.mode, sliderDays());
        resolve(mode);
      };
    });
  });
}

/* ------------------------------------------------------------------ import */

let pending = [];

function extractIds(text) {
  const ids = [];
  const seen = new Set();
  const push = (id) => {
    if (!seen.has(id)) {
      seen.add(id);
      ids.push(id);
    }
  };
  const re = /(?:youtube\.com\/(?:watch\?[^\s]*v=|shorts\/|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/g;
  let match;
  while ((match = re.exec(text))) {
    push(match[1]);
  }
  for (const token of text.split(/\s+/)) {
    if (/^[A-Za-z0-9_-]{11}$/.test(token) && /[0-9A-Z_-]/.test(token)) {
      push(token);
    }
  }
  return ids;
}

async function fetchMeta(videoId) {
  const watch = "https://www.youtube.com/watch?v=" + videoId;
  const url = "https://www.youtube.com/oembed?url=" + encodeURIComponent(watch) + "&format=json";
  const res = await fetch(url);
  if (!res.ok) {
    return null;
  }
  const json = await res.json();
  return { title: json.title || videoId, uploader: json.author_name || "Unknown uploader" };
}

async function fetchMetas(ids, status) {
  const metas = new Array(ids.length).fill(null);
  let next = 0;
  let done = 0;
  const lane = async () => {
    while (next < ids.length) {
      const i = next;
      next += 1;
      metas[i] = await fetchMeta(ids[i]).catch(() => null);
      done += 1;
      status.textContent = "Reading link " + done + " of " + ids.length +
        " through YouTube's oEmbed service";
    }
  };
  await Promise.all(Array.from({ length: Math.min(READ_CONCURRENCY, ids.length) }, lane));
  return metas;
}

async function readAndOrganise() {
  const status = $("read-status");
  const all = extractIds($("links").value);
  const existing = new Set(data.tracks.map((t) => t.videoId));
  let ids = all.filter((id) => !existing.has(id));
  const known = all.length - ids.length;
  if (!ids.length) {
    status.textContent = known
      ? "Those are already in your demo library."
      : "No YouTube links found. The demo cannot search by title, so paste full video links, one per line.";
    return;
  }
  const room = MAX_LIBRARY - data.tracks.length;
  if (room <= 0) {
    status.textContent = "The demo library holds " + MAX_LIBRARY +
      " songs at most. Remove some before adding more.";
    return;
  }
  const truncated = ids.length > room;
  ids = ids.slice(0, room);
  $("read-btn").disabled = true;
  const metas = await fetchMetas(ids, status);
  pending = ids.map((videoId, i) => {
    const meta = metas[i];
    if (!meta) {
      return { videoId, ok: false };
    }
    const sep = meta.title.indexOf(" - ");
    const artist = sep > 0 ? meta.title.slice(0, sep).trim() : meta.uploader;
    const title = sep > 0 ? meta.title.slice(sep + 3).trim() : meta.title;
    return { videoId, ok: true, title, artist, uploader: meta.uploader };
  });
  $("read-btn").disabled = false;
  const okCount = pending.filter((p) => p.ok).length;
  const bits = [okCount + " track" + (okCount === 1 ? "" : "s") + " organised"];
  if (known) {
    bits.push(known + " already in your library");
  }
  if (truncated) {
    bits.push("the demo holds " + MAX_LIBRARY + " songs at most, so only the first " +
      ids.length + " links were read");
  }
  status.textContent = bits.join(" · ");
  renderOrganised();
  if (okCount) {
    ensureWorker();
  }
}

function renderOrganised() {
  const box = $("organised");
  box.innerHTML = "";
  if (!pending.length) {
    return;
  }
  const list = document.createElement("ul");
  list.className = "rows";
  pending.forEach((row, i) => {
    const li = document.createElement("li");
    const title = document.createElement("span");
    title.className = "title" + (row.ok ? "" : " bad");
    title.textContent = row.ok ? row.title : "Could not read this video";
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = row.ok ? row.uploader : row.videoId;
    const x = document.createElement("button");
    x.className = "x";
    x.textContent = "✕";
    x.title = "Remove";
    x.onclick = () => {
      pending.splice(i, 1);
      renderOrganised();
    };
    li.append(title, who, x);
    list.appendChild(li);
  });
  const note = document.createElement("p");
  note.className = "hint";
  note.textContent = "Songs are grouped by uploader. The queue rests each uploader as well as " +
    "each song, the way the full app rests an artist or a topic.";
  const create = document.createElement("button");
  create.className = "btn primary";
  const okCount = pending.filter((p) => p.ok).length;
  create.textContent = (data.tracks.length ? "Add " : "Create the library with ") +
    okCount + " song" + (okCount === 1 ? "" : "s");
  create.disabled = !okCount;
  create.onclick = createLibrary;
  box.append(list, note, create);
  if (data.tracks.length) {
    const cancel = document.createElement("button");
    cancel.className = "btn";
    cancel.style.marginLeft = ".7rem";
    cancel.textContent = "Back to the player";
    cancel.onclick = () => showView("player");
    box.appendChild(cancel);
  }
}

async function createLibrary() {
  if (mode === null) {
    await showStoragePrompt();
  }
  for (const row of pending) {
    if (data.tracks.length >= MAX_LIBRARY) {
      break;
    }
    if (!row.ok || data.tracks.some((t) => t.videoId === row.videoId)) {
      continue;
    }
    let group = data.groups.find((g) => g.name.toLowerCase() === row.uploader.toLowerCase());
    if (!group) {
      group = { id: data.nextGroupId++, name: row.uploader };
      data.groups.push(group);
    }
    data.tracks.push({
      id: data.nextTrackId++, videoId: row.videoId, title: row.title,
      artist: row.artist, uploader: row.uploader, groupId: group.id, rating: null,
    });
  }
  pending = [];
  $("links").value = "";
  $("organised").innerHTML = "";
  $("read-status").textContent = "";
  persist();
  showView("player");
  await regenerateQueue($("read-status"));
  renderAll();
  loadCurrent(false);
}

/* ------------------------------------------------------------------ backup
   Export as a downloadable file, import by choosing one. The imported file is
   untrusted: every field is rebuilt by hand rather than merged, video ids must be
   exactly 11 safe characters, strings are trimmed and capped, ratings clamped to
   1..5 and the storage choice checked against the known modes. Nothing from a
   file is ever executed, fetched, or written into the page as markup. */

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
const STORAGE_MODES = ["session", "days", "local", "none"];
const MAX_IMPORT_BYTES = 1024 * 1024;
const MAX_LIBRARY = 500;

function cleanText(value, fallback) {
  if (typeof value !== "string") {
    return fallback;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, 200) : fallback;
}

function exportScope(scope) {
  const out = {
    format: "harmonica-demo-export",
    version: 1,
    scope,
    exportedAt: new Date().toISOString(),
  };
  if (scope === "all" || scope === "metadata") {
    out.metadata = {
      tracks: data.tracks.map((t) => ({
        videoId: t.videoId, title: t.title, artist: t.artist, uploader: t.uploader,
      })),
    };
  }
  if (scope === "all" || scope === "ratings") {
    out.ratings = data.tracks
      .filter((t) => t.rating != null)
      .map((t) => ({ videoId: t.videoId, rating: t.rating }));
  }
  if (scope === "all" || scope === "settings") {
    out.settings = {
      storage: mode === null ? null : { mode, days: mode === "days" ? modeDays : undefined },
      algorithm: Object.assign({}, data.settings),
    };
  }
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "harmonica-demo-" + scope + "-" + new Date().toISOString().slice(0, 10) + ".json";
  link.click();
  URL.revokeObjectURL(url);
}

async function importFromFile(file) {
  const el = $("view-import").hidden ? $("player-status") : $("read-status");
  if (file.size > MAX_IMPORT_BYTES) {
    el.textContent = "That file is larger than any demo export.";
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    el.textContent = "That file is not a demo export.";
    return;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    el.textContent = "That file is not a demo export.";
    return;
  }
  const summary = [];

  // Storage choice first, so a full restore does not also have to answer the cookie prompt.
  const settings = parsed.settings;
  const storage = settings && typeof settings === "object" && !Array.isArray(settings)
    ? settings.storage : null;
  if (storage && typeof storage === "object" && STORAGE_MODES.includes(storage.mode)) {
    applyStorageChoice(storage.mode, DAY_STOPS.includes(storage.days) ? storage.days : 30);
    summary.push("storage choice applied");
  }

  // Algorithm tuning: only known keys, clamped to each control's own range.
  const rawAlgorithm = settings && typeof settings === "object" && !Array.isArray(settings)
    ? settings.algorithm : null;
  let tuned = 0;
  if (rawAlgorithm && typeof rawAlgorithm === "object" && !Array.isArray(rawAlgorithm)) {
    for (const ctl of SETTING_CONTROLS) {
      const raw = rawAlgorithm[ctl.key];
      if (typeof ctl.def === "boolean" && typeof raw === "boolean") {
        setSetting(ctl, raw);
        tuned += 1;
      } else if (typeof ctl.def === "number" && typeof raw === "number" && Number.isFinite(raw)) {
        setSetting(ctl, Math.min(ctl.max, Math.max(ctl.min, raw)));
        tuned += 1;
      }
    }
  }
  if (tuned) {
    renderSettings();
    summary.push(tuned + " algorithm setting" + (tuned === 1 ? "" : "s"));
  }

  const meta = parsed.metadata && typeof parsed.metadata === "object" ? parsed.metadata : null;
  const rawTracks = meta && Array.isArray(meta.tracks) ? meta.tracks : [];
  let added = 0;
  for (const raw of rawTracks) {
    if (!raw || typeof raw !== "object" || data.tracks.length >= MAX_LIBRARY) {
      continue;
    }
    const videoId = typeof raw.videoId === "string" && VIDEO_ID_RE.test(raw.videoId)
      ? raw.videoId : null;
    if (!videoId || data.tracks.some((t) => t.videoId === videoId)) {
      continue;
    }
    const uploader = cleanText(raw.uploader, "Unknown uploader");
    let group = data.groups.find((g) => g.name.toLowerCase() === uploader.toLowerCase());
    if (!group) {
      group = { id: data.nextGroupId++, name: uploader };
      data.groups.push(group);
    }
    data.tracks.push({
      id: data.nextTrackId++, videoId, title: cleanText(raw.title, videoId),
      artist: cleanText(raw.artist, uploader), uploader, groupId: group.id, rating: null,
    });
    added += 1;
  }
  if (added) {
    summary.push(added + " song" + (added === 1 ? "" : "s"));
  }

  const rawRatings = Array.isArray(parsed.ratings) ? parsed.ratings : [];
  let starred = 0;
  for (const raw of rawRatings) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const track = typeof raw.videoId === "string"
      ? data.tracks.find((t) => t.videoId === raw.videoId) : null;
    const rating = Number(raw.rating);
    if (!track || !Number.isFinite(rating)) {
      continue;
    }
    track.rating = Math.min(5, Math.max(1, Math.round(rating)));
    starred += 1;
  }
  if (starred) {
    summary.push(starred + " rating" + (starred === 1 ? "" : "s"));
  }

  if (!summary.length) {
    el.textContent = "Nothing in that file could be used here.";
    return;
  }
  if ((added || starred) && mode === null) {
    await showStoragePrompt();
  }
  persist();
  const message = "Imported: " + summary.join(", ") + ".";
  if (data.tracks.length) {
    showView("player");
    if (added || !data.queue.length) {
      await regenerateQueue();
    }
    renderAll();
    loadCurrent(false);
    $("player-status").textContent = message;
  } else {
    el.textContent = message;
  }
}

/* ---------------------------------------------------------------- settings
   Real controls over the real algorithm. Every key except queue_length is a field of the
   driver's Settings class with the app's own default, and only values moved off their default
   are stored and sent, so the app stays the single source of truth for what normal means.
   The strength sliders double as switches: at 0 their multiplier collapses to exactly 1. */

const SETTING_CONTROLS = [
  { key: "queue_length", label: "Queue length", def: QUEUE_LEN, min: 5, max: 30, step: 1,
    expl: "How many songs each generated queue holds." },
  { key: "cold_start_enabled", label: "Unheard songs first", def: true,
    expl: "Prioritises songs that have never been played, so everything gets a first hearing " +
      "before anything is worn in." },
  { key: "satiation_strength", label: "Satiation guard", def: 0.5, min: 0, max: 2, step: 0.1,
    expl: "How firmly a song with heavy recent listening is rested. At 0 a binge has no " +
      "after-effect. At 2 a binged song needs a proper break before it returns." },
  { key: "rediscovery_strength", label: "Rediscovery", def: 0.4, min: 0, max: 1, step: 0.05,
    expl: "How strongly a well-rated song that has gone unheard for weeks is invited back." },
  { key: "skip_penalty_strength", label: "Skip penalty", def: 0.25, min: 0, max: 1, step: 0.05,
    expl: "How much skipping a song early counts against it. Skips near the end barely " +
      "count, and later full listens forgive old skips." },
  { key: "song_rating_max_multiplier", label: "Five-star boost", def: 2.0, min: 1, max: 3,
    step: 0.1,
    expl: "How many times more weight a five-star song carries than an unrated one. Ratings " +
      "below the neutral midpoint reduce weight instead." },
  { key: "group_clustering_bias", label: "Uploader clustering", def: 0.0, min: -1, max: 1,
    step: 0.1,
    expl: "Below zero spreads one uploader's songs apart. Above zero lets them arrive in " +
      "runs. The full app applies this to artists and topics." },
  { key: "beta", label: "Large-group weighting", def: 1.25, min: 0, max: 3, step: 0.25,
    expl: "How much extra draw an uploader gets for holding many songs. At 0 every uploader " +
      "gets an equal share of the queue, however big." },
];

function settingValue(ctl) {
  const stored = data.settings ? data.settings[ctl.key] : undefined;
  if (typeof ctl.def === "boolean") {
    return typeof stored === "boolean" ? stored : ctl.def;
  }
  return typeof stored === "number" && Number.isFinite(stored)
    ? Math.min(ctl.max, Math.max(ctl.min, stored))
    : ctl.def;
}

function setSetting(ctl, value) {
  if (!data.settings) {
    data.settings = {};
  }
  if (value === ctl.def) {
    delete data.settings[ctl.key];
  } else {
    data.settings[ctl.key] = value;
  }
  persist();
  $("settings-note").textContent = "Saved. The next queue is generated with these settings.";
}

function formatSetting(ctl, value) {
  if (typeof ctl.def === "boolean") {
    return value ? "on" : "off";
  }
  const text = String(Number(value.toFixed(2)));
  return ctl.min < 0 && value > 0 ? "+" + text : text;
}

function renderSettings() {
  const box = $("settings-list");
  box.innerHTML = "";
  for (const ctl of SETTING_CONTROLS) {
    const row = document.createElement("div");
    row.className = "setting";
    const label = document.createElement("label");
    label.textContent = ctl.label;
    label.htmlFor = "set-" + ctl.key;
    const input = document.createElement("input");
    input.id = "set-" + ctl.key;
    const val = document.createElement("span");
    val.className = "val";
    val.textContent = formatSetting(ctl, settingValue(ctl));
    if (typeof ctl.def === "boolean") {
      input.type = "checkbox";
      input.checked = settingValue(ctl);
      input.onchange = () => {
        setSetting(ctl, input.checked);
        val.textContent = formatSetting(ctl, input.checked);
      };
    } else {
      input.type = "range";
      input.min = ctl.min;
      input.max = ctl.max;
      input.step = ctl.step;
      input.value = settingValue(ctl);
      input.oninput = () => {
        setSetting(ctl, Number(input.value));
        val.textContent = formatSetting(ctl, Number(input.value));
      };
    }
    const expl = document.createElement("p");
    expl.className = "expl";
    expl.textContent = ctl.expl;
    row.append(label, input, val, expl);
    box.appendChild(row);
  }
}

function settingsPayload() {
  const overrides = {};
  for (const ctl of SETTING_CONTROLS) {
    const value = settingValue(ctl);
    if (ctl.key !== "queue_length" && value !== ctl.def) {
      overrides[ctl.key] = value;
    }
  }
  return overrides;
}

/* ------------------------------------------------------------------ python
   Pyodide lives in worker.js, on its own thread. Booting Python takes seconds and the page
   has only one thread of its own, so running it here froze scrolling; instead the page posts
   a message and stays responsive while the worker does the heavy lifting. */

let worker = null;
let workerReady = false;
let workerStatusEl = null;
let nextCallId = 1;
const workerCalls = new Map();

function injectScript(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.onload = resolve;
    el.onerror = () => reject(new Error("could not load " + src));
    document.head.appendChild(el);
  });
}

function ensureWorker() {
  if (!worker) {
    worker = new Worker("worker.js");
    worker.onmessage = (event) => {
      const msg = event.data || {};
      if (msg.ready) {
        workerReady = true;
        if (workerStatusEl && workerCalls.size) {
          workerStatusEl.textContent = "Generating a queue with the real algorithm";
        }
        return;
      }
      const call = workerCalls.get(msg.id);
      if (!call) {
        return;
      }
      workerCalls.delete(msg.id);
      if (msg.ok) {
        workerReady = true;
        call.resolve(msg.queue);
      } else {
        call.reject(new Error(msg.error));
      }
    };
    worker.onerror = () => {
      const waiting = [...workerCalls.values()];
      workerCalls.clear();
      worker.terminate();
      worker = null;
      workerReady = false;
      waiting.forEach((call) => call.reject(new Error("the queue worker could not run")));
    };
    worker.postMessage({ warm: true });
  }
  return worker;
}

function generateInWorker(payloadJson) {
  return new Promise((resolve, reject) => {
    const id = nextCallId;
    nextCallId += 1;
    workerCalls.set(id, { resolve, reject });
    ensureWorker().postMessage({ id, payload: payloadJson });
  });
}

async function regenerateQueue(statusEl) {
  if (!data.tracks.length) {
    data.queue = [];
    data.queueIndex = 0;
    persist();
    return;
  }
  const el = statusEl || $("player-status");
  workerStatusEl = el;
  try {
    el.textContent = workerReady
      ? "Generating a queue with the real algorithm"
      : "Loading the Python runtime, about 10 MB on the first visit, cached after that";
    const payload = {
      tracks: data.tracks.map((t) => ({
        id: t.id, videoId: t.videoId, title: t.title, artist: t.artist,
        uploader: t.uploader, groupId: t.groupId, rating: t.rating,
      })),
      groups: data.groups,
      events: data.events,
      length: settingValue(SETTING_CONTROLS[0]),
      settings: settingsPayload(),
      seed: Math.floor(Math.random() * 2147483647),
    };
    data.queue = JSON.parse(await generateInWorker(JSON.stringify(payload)));
    data.queueIndex = 0;
    el.textContent = "";
  } catch (err) {
    el.textContent = "The Python runtime could not be loaded. Check your connection and try again.";
    console.error(err);
  }
  workerStatusEl = null;
  persist();
}

/* ------------------------------------------------------------------ player */

let player = null;
let playerMounted = false;

function currentItem() {
  return data.queue[data.queueIndex] || null;
}

function trackById(id) {
  return data.tracks.find((t) => t.id === id) || null;
}

function mountPlayer() {
  if (!data.ytConsent || playerMounted) {
    return;
  }
  playerMounted = true;
  $("consent-gate").hidden = true;
  window.onYouTubeIframeAPIReady = () => {
    player = new YT.Player("yt-player", {
      width: "100%",
      height: "100%",
      videoId: currentItem() ? currentItem().videoId : undefined,
      playerVars: { playsinline: 1, rel: 0 },
      events: { onStateChange: onPlayerState, onError: onPlayerError },
    });
  };
  injectScript("https://www.youtube.com/iframe_api").catch(() => {
    $("player-status").textContent = "YouTube's player could not be loaded.";
  });
}

let errorStreak = 0;

function onPlayerState(event) {
  if (event.data === YT.PlayerState.PLAYING) {
    errorStreak = 0;
  }
  if (event.data === YT.PlayerState.ENDED) {
    recordEvent("completed");
    advance();
  }
}

function onPlayerError() {
  errorStreak += 1;
  if (errorStreak >= 5) {
    $("player-status").textContent = "Several videos in a row would not play here. " +
      "Press Play next when you want to try the following one.";
    return;
  }
  $("player-status").textContent = "That video would not play here. Moving on.";
  advance();
}

function recordEvent(eventType) {
  const item = currentItem();
  if (!item || !player || typeof player.getDuration !== "function") {
    return;
  }
  const duration = player.getDuration() || null;
  let progress = player.getCurrentTime() || 0;
  if (eventType === "completed" && duration) {
    progress = duration;
  }
  data.events.push({
    trackId: item.trackId, eventType, createdAt: new Date().toISOString(),
    durationSeconds: duration, progressSeconds: progress,
  });
  if (data.events.length > 800) {
    data.events = data.events.slice(-800);
  }
  persist();
}

function loadCurrent(autoplay) {
  const item = currentItem();
  if (!item || !player || typeof player.loadVideoById !== "function") {
    return;
  }
  if (autoplay) {
    player.loadVideoById(item.videoId);
  } else {
    player.cueVideoById(item.videoId);
  }
}

async function advance() {
  data.queueIndex += 1;
  if (data.queueIndex >= data.queue.length) {
    $("player-status").textContent = "Queue finished. Generating the next one from your listening so far";
    await regenerateQueue();
  }
  persist();
  renderAll();
  loadCurrent(true);
}

/* ------------------------------------------------------------------ render */

function showView(name) {
  $("view-import").hidden = name !== "import";
  $("view-player").hidden = name !== "player";
}

function renderStars(container, track, compact) {
  container.innerHTML = "";
  if (!track) {
    return;
  }
  for (let i = 1; i <= 5; i += 1) {
    const btn = document.createElement("button");
    btn.textContent = "★";
    btn.className = track.rating != null && track.rating >= i ? "on" : "";
    if (compact) {
      btn.style.fontSize = "1rem";
    }
    btn.title = i + " out of 5. Click your current rating again to clear it.";
    btn.onclick = () => {
      track.rating = track.rating === i ? null : i;
      persist();
      renderAll();
    };
    container.appendChild(btn);
  }
}

function whyReasons(item) {
  const ex = item.explanation || {};
  const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : 1);
  const reasons = [];
  const groups = (ex.group_contributions || [])
    .slice()
    .sort((a, b) => (b.contribution || 0) - (a.contribution || 0));
  const top = groups[0];
  if (top && top.name) {
    const size = top.size || 0;
    reasons.push("Drawn from " + top.name +
      (size > 0 ? " (" + size + " track" + (size === 1 ? "" : "s") + ")" : ""));
  }
  const boosts = [];
  const rating = num(ex.rating_multiplier);
  if (rating >= 1.15) {
    boosts.push([rating, "You rate this highly"]);
  }
  const rediscovery = num(ex.rediscovery_multiplier);
  if (rediscovery > 1.02) {
    boosts.push([rediscovery, "A favourite you haven't heard for a while"]);
  }
  const coldStart = num(ex.cold_start_multiplier);
  if (coldStart > 1.01) {
    boosts.push([coldStart, "New to you, played sooner so you can rate it"]);
  }
  boosts.sort((a, b) => b[0] - a[0]);
  if (boosts[0]) {
    reasons.push(boosts[0][1]);
  }
  const dampers = [];
  if (rating <= 0.85) {
    dampers.push([rating, "you rate it lower than most"]);
  }
  const satiation = num(ex.satiation_multiplier);
  if (satiation <= 0.92) {
    dampers.push([satiation, "it has been played a lot recently"]);
  }
  const songCooldown = num(ex.song_cooldown);
  if (songCooldown <= 0.6) {
    dampers.push([songCooldown, "you heard it recently"]);
  }
  const history = num(ex.history_multiplier);
  if (history <= 0.95) {
    dampers.push([history, "you skipped it recently"]);
  }
  const cooled = groups
    .filter((g) => g.name && typeof g.cooldown === "number")
    .sort((a, b) => a.cooldown - b.cooldown)[0];
  if (cooled && cooled.cooldown <= 0.5) {
    dampers.push([cooled.cooldown, cooled.name + " has been played a lot recently"]);
  }
  dampers.sort((a, b) => a[0] - b[0]);
  if (dampers[0]) {
    reasons.push("Coming up less often right now: " + dampers[0][1]);
  }
  if (!reasons.length) {
    reasons.push("A balanced pick for variety");
  }
  return reasons;
}

function renderPlayer() {
  const item = currentItem();
  const track = item ? trackById(item.trackId) : null;
  $("now-title").textContent = item ? item.title : "Nothing queued";
  $("now-artist").textContent = item
    ? [item.artist, item.uploader].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).join(" · ")
    : "";
  renderStars($("now-stars"), track, false);
  const why = $("now-why");
  why.innerHTML = "";
  if (item) {
    for (const line of whyReasons(item)) {
      const li = document.createElement("li");
      li.textContent = line;
      why.appendChild(li);
    }
  }
}

function renderQueue() {
  const list = $("queue-list");
  list.innerHTML = "";
  data.queue.forEach((item, i) => {
    const li = document.createElement("li");
    if (i === data.queueIndex) {
      li.className = "current";
    }
    const n = document.createElement("span");
    n.className = "n";
    n.textContent = i + 1;
    const t = document.createElement("span");
    t.className = "t";
    t.textContent = item.title;
    const u = document.createElement("span");
    u.className = "u";
    u.textContent = item.uploader || "";
    li.append(n, t, u);
    li.onclick = () => {
      if (i === data.queueIndex) {
        return;
      }
      recordEvent("skipped");
      data.queueIndex = i;
      persist();
      renderAll();
      loadCurrent(true);
    };
    list.appendChild(li);
  });
}

function renderLibrary() {
  $("lib-count").textContent = data.tracks.length;
  const list = $("library-list");
  list.innerHTML = "";
  for (const track of data.tracks) {
    const li = document.createElement("li");
    const title = document.createElement("span");
    title.className = "title";
    title.textContent = track.title;
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = track.uploader;
    const stars = document.createElement("span");
    stars.className = "stars";
    renderStars(stars, track, true);
    const x = document.createElement("button");
    x.className = "x";
    x.textContent = "✕";
    x.title = "Remove from the demo library";
    x.onclick = () => removeTrack(track.id);
    li.append(title, who, stars, x);
    list.appendChild(li);
  }
  const plays = data.events.length;
  $("statsline").textContent = data.tracks.length + " songs · " + data.groups.length +
    " uploader" + (data.groups.length === 1 ? "" : "s") + " · " + plays +
    " listening event" + (plays === 1 ? "" : "s") + " recorded in this browser";
}

function removeTrack(trackId) {
  const wasCurrent = currentItem() && currentItem().trackId === trackId;
  const currentRef = currentItem();
  data.tracks = data.tracks.filter((t) => t.id !== trackId);
  data.groups = data.groups.filter((g) => data.tracks.some((t) => t.groupId === g.id));
  data.queue = data.queue.filter((item) => item.trackId !== trackId);
  if (!wasCurrent && currentRef) {
    data.queueIndex = Math.max(0, data.queue.indexOf(currentRef));
  } else {
    data.queueIndex = Math.min(data.queueIndex, Math.max(0, data.queue.length - 1));
  }
  persist();
  if (!data.tracks.length) {
    showView("import");
    renderAll();
    return;
  }
  renderAll();
  if (wasCurrent) {
    loadCurrent(false);
  }
}

function renderAll() {
  renderPlayer();
  renderQueue();
  renderLibrary();
}

/* -------------------------------------------------------------------- init */

function init() {
  initStorage();
  renderSettings();
  $("read-btn").onclick = readAndOrganise;
  $("consent-btn").onclick = () => {
    data.ytConsent = true;
    persist();
    mountPlayer();
  };
  $("next-btn").onclick = () => {
    recordEvent("skipped");
    advance();
  };
  $("requeue-btn").onclick = async () => {
    $("settings-note").textContent = "";
    await regenerateQueue();
    renderAll();
    loadCurrent(false);
  };
  $("settings-defaults").onclick = () => {
    data.settings = {};
    persist();
    renderSettings();
    $("settings-note").textContent = "Back to the app's own defaults.";
  };
  $("add-more").onclick = () => {
    showView("import");
    $("read-status").textContent = "New links are added to your existing library.";
  };
  $("reset-demo").onclick = () => {
    if (confirm("Forget everything the demo has stored in this browser?")) {
      localStorage.removeItem(META_KEY);
      localStorage.removeItem(DATA_KEY);
      sessionStorage.removeItem(META_KEY);
      sessionStorage.removeItem(DATA_KEY);
      location.reload();
    }
  };
  $("storage-link").onclick = (event) => {
    event.preventDefault();
    showStoragePrompt();
  };
  $("days-range").oninput = () => {
    const days = sliderDays();
    $("days-btn").textContent = "For " + days + " day" + (days === 1 ? "" : "s");
  };
  document.querySelectorAll("button[data-export]").forEach((btn) => {
    btn.onclick = () => exportScope(btn.dataset.export);
  });
  const pickFile = () => $("import-file").click();
  $("import-btn").onclick = pickFile;
  $("restore-btn").onclick = pickFile;
  $("import-file").onchange = (event) => {
    const file = event.target.files && event.target.files[0];
    event.target.value = "";
    if (file) {
      importFromFile(file);
    }
  };

  if (data.tracks.length) {
    showView("player");
    renderAll();
    if (data.ytConsent) {
      mountPlayer();
    }
    if (!data.queue.length) {
      regenerateQueue().then(() => {
        renderAll();
        loadCurrent(false);
      });
    }
  } else {
    showView("import");
  }
}

init();
