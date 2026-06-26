/* Harmonica service worker — app-shell caching for a fast, reliable standalone
 * launch on the iPhone home screen. Deliberately conservative:
 *   - Caches only the static shell (navigations + hashed JS/CSS/icons/fonts).
 *   - NEVER caches the API or /media (those must stay live from the daemon),
 *     and never caches non-GET or cross-origin requests.
 * Bump CACHE when the shell contract changes to evict the old cache.
 */
const CACHE = "harmonica-shell-v1";

// Same-origin paths that must always hit the network (live data + big media).
const BYPASS = [
  "/health", "/settings", "/rating-factors", "/groups", "/tracks", "/scan",
  "/queue", "/playlist-runs", "/media", "/library", "/stats", "/playback-events",
  "/configs",
];

self.addEventListener("install", (event) => {
  // Pre-cache the entry document so the app opens even on a flaky connection.
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(["/", "/index.html"]))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

function isShellAsset(url) {
  if (url.pathname === "/" || url.pathname === "/index.html") return true;
  if (url.pathname.startsWith("/assets/")) return true; // Vite-hashed JS/CSS
  return /\.(js|css|svg|png|ico|webmanifest|woff2?)$/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (BYPASS.some((p) => url.pathname.startsWith(p))) return;

  // Navigations: network-first so a fresh deploy wins, fall back to cached shell.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("/index.html", copy));
          return res;
        })
        .catch(() => caches.match("/index.html").then((r) => r || caches.match("/")))
    );
    return;
  }

  if (!isShellAsset(url)) return;

  // Hashed assets: cache-first (their URL changes when content changes).
  event.respondWith(
    caches.match(request).then((hit) => {
      if (hit) return hit;
      return fetch(request).then((res) => {
        if (res.ok && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
        }
        return res;
      });
    })
  );
});
