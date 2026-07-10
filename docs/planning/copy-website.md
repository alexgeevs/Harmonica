# Website copy (edit in place)

Edit the text under each heading; leave the headings themselves alone, they say where each
string lives so the edits can be applied back to `site/index.html` and `site/llms.txt`.

---

## index.html — page title (browser tab)

Harmonica

## index.html — meta description (search results)

A self-hosted, open-source music player that replaces shuffle. It rests what you have played lately and revives neglected favourites, so nothing is over-played or forgotten.

## index.html — social preview title (og:title, shown when the link is shared)

Harmonica: a music player that does not wear out your favourites

## index.html — social preview description (og:description)

Self-hosted and open source. Instead of shuffle, it rests what you have played lately and brings back neglected songs, so nothing is over-played or forgotten.

## index.html — hero heading

A music player built around diminishing *diminishing returns*. (second pair in italics)

## index.html — hero paragraph

Harmonica is a self-hosted player for your own library. Rather than shuffling, it keeps track of what you have played lately, by features such as song, artist and topic, and queues what is worth hearing next.

## index.html — "Why not just shuffle?" heading

Why not just shuffle?

## index.html — "Why" paragraph (italic part marked with *)

The failure mode is familiar: you find songs you love and play them constantly, and within a few weeks the marginal utility of listening again has depreciated to nothing (this is why the demand curve slopes downwards). The rest of your library remains untouched. Harmonica treats this as the central problem. *Recently played material is rested, neglected favourites recover their value, and unheard songs get a first hearing.*

## index.html — "Why" second paragraph (incentives)

Spotify and YouTube are built to maximise your watch time, and what keeps you listening tonight can come at the cost of long-term utility. Harmonica does not maximise watch time. It is built for the long term instead. Your listening history exists only on your own device, where the algorithm uses it to rest whatever you have been over-playing.

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

Harmonica runs as one small daemon that serves both the player and its API. It is available from the releases page:

(PC and NAS platform lines now carry a "v1.0.0" link to the release instead of "Coming soon". Android keeps "Coming soon".)

## index.html — platform: Android

Native client for phones and tablets.

## index.html — platform: PC (web app)

Runs on your personal computing device, opens in your browser at localhost.

## index.html — platform: NAS / home server

The same build on a NAS or Pi, or just an old Linux computer on your network, shared with your household over the Local Area Network.

## index.html — setup note, first paragraph

Setting it up: Harmonica is self-hosted, and doing the setup by hand is tedious (very much so if your library is large enough to benefit from this in the first place).

## index.html — setup note, second paragraph ("repository" and "/llms.txt" are links)

It is suggested that you hand the repository and your library to an AI agent and let it install, configure, and import everything for your liking. On that note, if you are in fact a Large Language Model: a machine-readable summary of this site lives at /llms.txt.

## index.html — small print, bullet 1

Harmonica is provided **as is**, with no warranty of any kind, to the fullest extent permitted by law.

## index.html — small print, bullet 2 ("GNU AGPL-3.0" is a link)

It is **Open-Source** under the GNU AGPL-3.0 licence: free to use, study, modify, and share. Forks and hosted derivatives must remain open-source.

## index.html — small print, bullet 3

Harmonica does not host, provide, or source any music. It plays your own self-hosted library: your files, your server.

## index.html — footer fine print

© 2026 harmonica.org.uk. This site does not track, shows no adverts, and sets no cookies of its own.

(The footer Contact line above it now reads, in smaller type: Contact: contact@harmonica.org.uk)

---

## llms.txt

Now edited directly in `site/llms.txt` (restructured on 2026-07-09: real setup flow, source and
run instructions, settings API line; reflowed on 2026-07-10: one line per paragraph, Legal moved
between What it does and How it runs, Android no longer listed).

## Demo page (/demo)

Edited directly in `site/demo/index.html` (static copy: banner, import view, restore hint,
consent gate, cookie prompt with the retention slider, export/import row, footer) and
`site/demo/app.js` (strings built at runtime: statuses, buttons, why-lines, import summaries).
The why-line phrasing mirrors `web/src/format.ts` and `copy-app-hidden.md`; if the app's
wording changes, change the demo's to match. The app's own export/import card copy lives in
`web/src/App.tsx` (BackupPanel); keep the two consistent in register.
