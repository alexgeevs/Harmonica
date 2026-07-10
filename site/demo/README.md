# In-browser demo

A static demonstration of Harmonica's queueing algorithm, served at `/demo` on the website.
Visitors paste YouTube links, the page reads each video's title and uploader through YouTube's
oEmbed endpoint, and the repo's real `algorithm.py`, `history.py` and `ratings.py` generate the
queue in the browser through Pyodide. Playback goes through YouTube's official embedded player
behind a consent gate. Everything the visitor builds (links, ratings, listening history) stays
in their own browser storage, behind a working cookie-style prompt that asks how long to keep it.

## Layout

- `index.html`, `app.js` — the whole page. Plain JS, no framework, no build step.
- `py/driver.py` — stubs `sqlalchemy` and the `harmonica.config`/`harmonica.models` imports so
  the real algorithm files load unchanged, rebuilds the inputs `playlist.py` would read from the
  database, and returns the generated queue as JSON.
- `py/algorithm.py`, `py/history.py`, `py/ratings.py` — NOT committed. The Pages workflow copies
  them from `src/harmonica/` at deploy so the demo can never drift from the app.

## Previewing locally

```bash
cp src/harmonica/algorithm.py src/harmonica/history.py src/harmonica/ratings.py site/demo/py/
python3 -m http.server 8899 --directory site
# open http://127.0.0.1:8899/demo/
```

The copies are gitignored. Pyodide loads from the jsDelivr CDN, so previewing needs a connection.

## demo.harmonica.org.uk

GitHub Pages serves one domain per site, so the subdomain is DNS configuration rather than code:
either a Cloudflare redirect rule from `demo.harmonica.org.uk/*` to `harmonica.org.uk/demo/`, or
a second Pages repo with its own CNAME. The page works at `/demo` either way.
