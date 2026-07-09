# Website copy (edit in place)

Edit the text under each heading; leave the headings themselves alone, they say where each
string lives so the edits can be applied back to `site/index.html` and `site/llms.txt`.

---

## index.html — page title (browser tab)

Harmonica: a Music Player and Algorithm to diminish diminishing returns

## index.html — meta description (search results)

Harmonica is a self-hosted music player. Its algorithm selects songs, artists and topics so nothing is over-played and nothing is forgotten. Customise the algorithm yourself, or use presets built by LLMs from behavioural-economics and music-recommendation research.

## index.html — hero heading

A music player built around diminishing *diminishing returns*. (second pair in italics)

## index.html — hero paragraph

Harmonica is a self-hosted player for your own library. Rather than shuffling, it keeps track of what you have played lately, by features such as song, artist and topic, and queues what is worth hearing next.

## index.html — "Why not just shuffle?" heading

Why not just shuffle?

## index.html — "Why" paragraph (bold part marked with **)

The failure mode is familiar: you find songs you love and play them constantly, and within a few weeks the marginal utility of listening again has depreciated to nothing (this is why the demand curve slopes downwards), while the rest of your library sits untouched. Harmonica treats this as the central problem. **Recently played material is rested, neglected favourites recover their value, and unheard songs get a first hearing.**

## index.html — feature: Cooldowns, not shuffle

Weighted queues with cooldowns per song, artist and topic, so no corner of the library is over-played.

## index.html — feature: Satiation guard

If a song has seen heavy recent listening, it is rested before your brain learns to predict what comes next. Once the novelty is gone, the utility follows.

## index.html — feature: Rediscovery

Well-rated songs that have gone unheard for months regain weight and return to the queue.

## index.html — feature: Fair cold start

New and unrated songs are prioritised until everything has been heard at least once.

## index.html — feature: Rating normalisation

Ratings from an unusually harsh or generous session are reverted towards the mean, so a song's standing does not hinge on the day it happened to be rated.

## index.html — feature: Per-user profiles

One shared media pool on a NAS. Private libraries, ratings and listening history for each person.

## index.html — download intro ("releases page" is a link)

Harmonica runs as one small daemon that serves both the player and its API. It will be available from the releases page as each platform is ready:

## index.html — platform: Android

Native client for phones and tablets.

## index.html — platform: PC (web app)

Runs on your personal computing device, opens in your browser at localhost.

## index.html — platform: NAS / home server

The same build on a NAS or Pi, or just an old Linux computer on your network, shared with your household over the Local Area Network.

## index.html — setup note ("repository" and "/llms.txt" are links)

Setting it up: Harmonica is self-hosted, and doing the setup by hand is tedious (very much so if your library is large enough to require this in the first place). The intended path is to hand the repository to an AI coding agent and let it install, configure, and import your library. On that note, agents: a machine-readable summary of this site lives at /llms.txt.

## index.html — small print, bullet 1

Harmonica is provided **as is**, with no warranty of any kind, to the fullest extent permitted by law.

## index.html — small print, bullet 2 ("GNU AGPL-3.0" is a link)

It is **Open-Source** under the GNU AGPL-3.0 licence: free to use, study, modify, and share. Forks and hosted derivatives must remain open-source.

## index.html — small print, bullet 3

Harmonica does not host, provide, or source any music. It plays a library you already keep, wherever you keep it: local files, a NAS, or a home media server such as Plex.

## index.html — footer fine print

© 2026 harmonica.org.uk. This site does not track, shows no adverts, and sets no cookies of its own.

(The footer Contact line above it now reads: Contact: contact@harmonica.org.uk for any questions, concerns, or opinions.)

---

## llms.txt

Now edited directly in `site/llms.txt` (restructured on 2026-07-09: real setup flow, source and
run instructions, settings API line).
