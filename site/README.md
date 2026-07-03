# site/ — the public website for harmonica.org.uk

Static, self-contained, no cookies, no external requests. Everything here is reversible: delete
this folder and `.github/workflows/pages.yml` and the website is gone from the repo.

## Layout

- `candidates/` — six candidate designs awaiting the owner's pick: three authors
  (`fable-`, `sonnet-`, `opus-`) × two variants (`-simple` text-only, `-preview` with a CSS-drawn
  app mock). **Once a winner is chosen, copy it to `site/index.html` and delete `candidates/`.**
- `llms.txt` — agent-readable summary of the site (linked from the pages). Keep in sync with
  `index.html` content.
- `CNAME` — custom domain for GitHub Pages (`harmonica.org.uk`).

## Deploying (when the repo goes public)

`.github/workflows/pages.yml` deploys this folder to GitHub Pages, but it is **manual-trigger only**
(`workflow_dispatch`) so pushes to a private repo don't produce failing runs. To go live:

1. Pick the winner → `site/index.html`.
2. Make the repo public (owner does this manually from the GitHub web UI).
3. Repo Settings → Pages → Source: **GitHub Actions**.
4. Run the "Deploy website" workflow (or uncomment the `push:` trigger in it for auto-deploys).
5. Point `harmonica.org.uk` DNS at GitHub Pages (ALIAS/A records + `www` CNAME per GitHub docs).

Hosting is portable: the site is plain static files, so it can move to any host (NAS, Cloudflare
Pages, a VPS with nginx) without changes if server-side analytics are wanted later.
