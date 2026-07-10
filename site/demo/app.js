"use strict";

/* Harmonica demo. Plain JS on purpose: no framework, no build step, three static files.
   The queue itself comes from the repo's real algorithm files, run through Pyodide. */

const META_KEY = "harmonica.demo.meta";
const DATA_KEY = "harmonica.demo.data";
const QUEUE_LEN = 12;
const MAX_LINKS = 100;
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js";
const PY_FILES = ["algorithm.py", "history.py", "ratings.py"];

const $ = (id) => document.getElementById(id);

function blankData() {
  return {
    tracks: [], groups: [], events: [], queue: [], queueIndex: 0,
    ytConsent: false, nextTrackId: 1, nextGroupId: 1,
  };
}

/* ---------------------------------------------------------------- storage
   The cookie prompt is real: the user picks where the demo's data lives and
   for how long. "none" keeps everything in memory and forgets it on leave. */

let mode = null; // null = not asked yet | "none" | "session" | "local30" | "local"
let data = blankData();

function initStorage() {
  try {
    const localMeta = JSON.parse(localStorage.getItem(META_KEY) || "null");
    if (localMeta && (localMeta.mode === "local" || localMeta.mode === "local30")) {
      if (localMeta.expiresAt && Date.now() > localMeta.expiresAt) {
        localStorage.removeItem(META_KEY);
        localStorage.removeItem(DATA_KEY);
      } else {
        mode = localMeta.mode;
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
    } else if (mode === "local" || mode === "local30") {
      localStorage.setItem(DATA_KEY, JSON.stringify(data));
    }
  } catch {
    /* storage full or blocked: the demo keeps running in memory */
  }
}

function applyStorageChoice(newMode) {
  localStorage.removeItem(META_KEY);
  localStorage.removeItem(DATA_KEY);
  sessionStorage.removeItem(META_KEY);
  sessionStorage.removeItem(DATA_KEY);
  mode = newMode;
  if (mode === "local" || mode === "local30") {
    const expiresAt = mode === "local30" ? Date.now() + 30 * 86400000 : null;
    localStorage.setItem(META_KEY, JSON.stringify({ mode, expiresAt }));
  } else if (mode === "session") {
    sessionStorage.setItem(META_KEY, JSON.stringify({ mode }));
  }
  persist();
}

function showStoragePrompt() {
  const modal = $("storage-modal");
  modal.hidden = false;
  return new Promise((resolve) => {
    modal.querySelectorAll("button[data-mode]").forEach((btn) => {
      btn.onclick = () => {
        modal.hidden = true;
        applyStorageChoice(btn.dataset.mode);
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

async function readAndOrganise() {
  const status = $("read-status");
  const all = extractIds($("links").value);
  const existing = new Set(data.tracks.map((t) => t.videoId));
  let ids = all.filter((id) => !existing.has(id));
  const known = all.length - ids.length;
  if (!ids.length) {
    status.textContent = known
      ? "Those are already in your demo library."
      : "No YouTube links found. Paste full video links, one per line.";
    return;
  }
  const truncated = ids.length > MAX_LINKS;
  ids = ids.slice(0, MAX_LINKS);
  $("read-btn").disabled = true;
  status.textContent = "Reading " + ids.length + " link" + (ids.length === 1 ? "" : "s") +
    " through YouTube's oEmbed service";
  const metas = await Promise.all(ids.map((id) => fetchMeta(id).catch(() => null)));
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
    bits.push("only the first " + MAX_LINKS + " links were read, import these then paste the rest");
  }
  status.textContent = bits.join(" · ");
  renderOrganised();
  if (okCount) {
    ensurePython().catch(() => {});
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

/* ------------------------------------------------------------------ python */

let pyPromise = null;

function injectScript(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.onload = resolve;
    el.onerror = () => reject(new Error("could not load " + src));
    document.head.appendChild(el);
  });
}

function ensurePython() {
  if (!pyPromise) {
    pyPromise = (async () => {
      await injectScript(PYODIDE_URL);
      const py = await loadPyodide();
      py.FS.mkdirTree("/harmonica_src");
      for (const name of PY_FILES) {
        const res = await fetch("py/" + name);
        if (!res.ok) {
          throw new Error("missing py/" + name);
        }
        py.FS.writeFile("/harmonica_src/" + name, await res.text());
      }
      const driver = await (await fetch("py/driver.py")).text();
      py.runPython(driver);
      return py.globals.get("generate_queue");
    })();
    pyPromise.catch(() => {
      pyPromise = null;
    });
  }
  return pyPromise;
}

async function regenerateQueue(statusEl) {
  if (!data.tracks.length) {
    data.queue = [];
    data.queueIndex = 0;
    persist();
    return;
  }
  const el = statusEl || $("player-status");
  try {
    if (!pyPromise) {
      el.textContent = "Loading the Python runtime, about 10 MB on the first visit, cached after that";
    }
    const generate = await ensurePython();
    el.textContent = "Generating a queue with the real algorithm";
    const payload = {
      tracks: data.tracks.map((t) => ({
        id: t.id, videoId: t.videoId, title: t.title, artist: t.artist,
        uploader: t.uploader, groupId: t.groupId, rating: t.rating,
      })),
      groups: data.groups,
      events: data.events,
      length: QUEUE_LEN,
      seed: Math.floor(Math.random() * 2147483647),
    };
    data.queue = JSON.parse(generate(JSON.stringify(payload)));
    data.queueIndex = 0;
    el.textContent = "";
  } catch (err) {
    el.textContent = "The Python runtime could not be loaded. Check your connection and try again.";
    console.error(err);
  }
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
    await regenerateQueue();
    renderAll();
    loadCurrent(false);
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
