# site/ — the public website for harmonica.org.uk

Static, self-contained, no cookies, no external requests. Everything here is reversible: delete
this folder and `.github/workflows/pages.yml` and the website is gone from the repo.

## Layout

- `index.html` — the live page (owner picked the Fable simple design, 2026-07-03; all preview/mock
  variants were rejected). `candidates/opus-simple.html` is kept as the runner-up for reference —
  delete it once the design settles.
- `llms.txt` — agent-readable summary of the site (linked from the pages). Keep in sync with
  `index.html` content.
- `CNAME` — custom domain for GitHub Pages (`harmonica.org.uk`).

## Deploying (when the repo goes public)

`.github/workflows/pages.yml` deploys this folder to GitHub Pages, but it is **manual-trigger only**
(`workflow_dispatch`) so pushes to a private repo don't produce failing runs. To go live:

1. Make the repo public (owner does this manually from the GitHub web UI).
2. Repo Settings → Pages → Source: **GitHub Actions**.
3. Run the "Deploy website" workflow (or uncomment the `push:` trigger in it for auto-deploys).
4. Point `harmonica.org.uk` DNS at GitHub Pages (ALIAS/A records + `www` CNAME per GitHub docs).

Hosting is portable: the site is plain static files, so it can move to any host (NAS, Cloudflare
Pages, a VPS with nginx) without changes if server-side analytics are wanted later.
