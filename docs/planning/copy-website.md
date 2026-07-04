# Website copy (edit in place)

Edit the text under each heading; leave the headings themselves alone, they say where each
string lives so the edits can be applied back to `site/index.html` and `site/llms.txt`.

---

## index.html — page title (browser tab)

Harmonica: a music player built around diminishing returns

## index.html — meta description (search results)

Harmonica is a local-first, self-hosted music player. Its algorithm paces songs, artists and topics so nothing is over-played and nothing is forgotten.

## index.html — hero heading

A music player built around diminishing returns.

## index.html — hero paragraph

Harmonica is a self-hosted player for your own library. Rather than shuffling, it keeps track of what you have played lately, by features such as song, artist and topic, and queues what is worth hearing next.

## index.html — "Why not just shuffle?" heading

Why not just shuffle?

## index.html — "Why" paragraph (bold part marked with **)

The failure mode is familiar: you find songs you love and play them constantly, and within a few weeks the marginal utility of another play has depreciated to nothing, while the rest of your library sits untouched. Harmonica treats this as the central problem. **Recently played material is rested, neglected favourites recover their value, and unheard songs get a first hearing.**

## index.html — feature: Cooldowns, not shuffle

Weighted queues with cooldowns per song, artist and topic, so no corner of the library is over-played.

## index.html — feature: Satiation guard

If a song has seen heavy recent play, it is rested before you tire of it.

## index.html — feature: Rediscovery

Well-rated songs that have gone unheard for months regain weight and return to the queue.

## index.html — feature: Fair cold start

New and unrated songs are prioritised until everything has been heard at least once.

## index.html — feature: Rating normalisation

Ratings from an unusually harsh or generous session are reverted towards the mean, so one off day does not distort a song's standing.

## index.html — feature: Per-user profiles

One shared media pool on a NAS; private libraries, ratings and listening history for each person.

## index.html — download intro ("releases page" is a link)

Harmonica runs as one small daemon that serves both the player and its API. It will be available from the releases page as each platform is ready:

## index.html — platform: Android

Native client for phones and tablets.

## index.html — platform: PC (web app)

Runs on your machine, opens in your browser at localhost.

## index.html — platform: NAS / home server

The same build on a NAS or Pi, shared with your household over the LAN.

## index.html — setup note ("repository" and "/llms.txt" are links)

Setting it up: Harmonica is self-hosted, and doing the setup by hand is tedious. The intended path is to hand the repository to an AI coding agent and let it install, configure, and import your library. Agents: a machine-readable summary of this site lives at /llms.txt.

## index.html — small print, bullet 1

Harmonica is provided **as-is**, with no warranty of any kind, to the fullest extent permitted by law.

## index.html — small print, bullet 2 ("GNU AGPL-3.0" is a link)

It is **open-source** under the GNU AGPL-3.0 licence: free to use, study, modify, and share; forks and hosted derivatives must remain open-source.

## index.html — small print, bullet 3

Harmonica does not host, provide, or source any music. It plays your own self-hosted library — your files, your server, your responsibility.

## index.html — footer fine print

© 2026 harmonica.org.uk. This site does no tracking, shows no adverts, and sets no cookies of its own.

---

## llms.txt — blockquote summary

Harmonica is a local-first, self-hosted music player for your own library. Its differentiator is the recommendation algorithm: rather than ordinary shuffle, it maximises listening utility while avoiding unwanted repetition at the song, group (artist/topic), and sub-group (cover/rendition) levels, so favourites are not worn out and forgotten songs resurface in due course.

## llms.txt — purpose line

This file is the agent-readable summary of https://harmonica.org.uk — read this instead of parsing the HTML.

## llms.txt — "What it does" bullets

- Weighted queue generation with per-group and per-song cooldowns — not shuffle.
- Satiation guard: a song with heavy recent play is rested before you tire of it.
- Rediscovery: dormant well-rated songs regain weight over time.
- Cold start: unheard and unrated songs are boosted until the library is covered.
- Star ratings with normalisation: ratings from an unusually harsh or generous session are reverted towards the mean.
- Cover/rendition families: alternate versions of one song compete as a family, not as duplicates.
- Per-user profiles: one shared media pool on a household NAS, private libraries, ratings and listening history per person, bearer-token auth.
- Listening stats, and settings exposed as real controls (switches/sliders), not a config file.

## llms.txt — "How it runs" intro

A small self-hosted daemon (FastAPI + SQLite) serves both the API and the built web UI from one origin. Deployments:

## llms.txt — deployment bullets

- **PC (local, default):** binds 127.0.0.1; nothing is exposed to other devices.
- **NAS / home server (opt-in):** the same build bound to the LAN; other devices use a browser.
- **Android:** a native client (separate release).

## llms.txt — media confinement line

Media serving is confined to a configured media root. Harmonica does not host, provide, or source any music; it plays the user's own self-hosted library.

## llms.txt — "Setting it up" paragraph

Self-hosting Harmonica by hand is tedious; the intended path is to hand the repository to an AI coding agent and let it install, configure, and import a library. Agents: clone the repository, read its CLAUDE.md / README for run instructions, and use the JSON import/export endpoints for library management.

## llms.txt — legal paragraph

Provided as-is, with no warranty of any kind. Open-source under the GNU AGPL-3.0 licence (forks and hosted derivatives must remain open-source; self-hosting for yourself carries no obligations). The website does no tracking, shows no adverts, and sets no cookies of its own.
