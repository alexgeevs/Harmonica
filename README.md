# Harmonica

Harmonica is a self-hosted, open-source music player. Rather than replaying the same few
favourites until they wear out, it rests what you have heard lately and brings back what you have
not, so nothing is over-played and nothing is forgotten.

The big platforms maximise watch time, which can come at the cost of long-term enjoyment.
Harmonica gains nothing from your watch time, and does not maximise it.

Website: https://harmonica.org.uk

## What it does

- **Cooldowns, not shuffle.** Weighted queues with cooldowns per song, artist, and topic, so no
  corner of the library is over-played.
- **Satiation guard.** A song that has seen heavy recent play is rested before the novelty, and
  with it the utility, drains away. The plays age out and the song returns.
- **Rediscovery.** A song you rated above your library's average regains weight the longer it goes
  unheard, and returns to the queue months later. The boost resets the moment it plays.
- **Fair cold start.** New and unrated songs are prioritised until everything has been heard at
  least once.
- **Reversion to the mean.** Ratings from an unusually harsh or generous session are pulled back
  towards the mean, so a song's standing does not hinge on the day it happened to be rated.
- **Covers and renditions.** Alternate versions of one song (covers, reprises, live cuts) compete
  as a family rather than clutter the library as duplicates.
- **Per-user profiles.** On a household NAS, one shared media pool with private libraries,
  ratings, and listening history per person.
- **Wholly customisable.** Every parameter of the algorithm is a real control, a switch or slider
  that explains what it does. Nothing is fixed behind the scenes. The algorithm can be tuned
  completely, from cooldown lengths to the rating maths, and the whole player is a JSON API that
  anything can drive or build on.

## Your music stays yours

Harmonica does not host, provide, or source any music. It plays your own library, from your own
files, on your own server.

## Running it

The quickest path is an installer from the
[releases page](https://github.com/alexgeevs/Harmonica/releases): download the one for your
platform and run it. It fetches Harmonica into your home folder, sets it up, and starts it.

If you already have the repository (Code → Download ZIP, or `git clone`):

- **Windows:** double-click `start-harmonica.bat`.
- **Linux and macOS:** run `./start-harmonica.sh`.

The script installs what is missing, builds the player, and opens it in your browser at
`http://localhost:8765`. It is safe to run again at any time. For a large library the recommended
path is to hand this repository to an AI agent and let it do the setup and the import for you (see
the end of this file).

### Where it runs

- **PC (local, default):** binds `127.0.0.1`, so nothing is exposed to other devices.
- **NAS or home server (opt-in):** the same build bound to the LAN with `HARMONICA_HOST=0.0.0.0`,
  shared with the household, with private per-person profiles. Never the default.

## Contributing

Bugs and patches are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licence

Copyright © 2026 harmonica.org.uk. Free software under the GNU Affero General Public License v3.0
or later (see [`LICENSE`](LICENSE)). Provided as is, with no warranty of any kind. Forks and hosted
derivatives must remain open source. Self-hosting for yourself carries no obligations.

## For AI agents

Start with [`AGENTS.md`](AGENTS.md). It covers setup, importing the user's library, curation, and
composing settings, all through the JSON API. Field-level guides live in `docs/agents/`, and a
machine-readable summary of the website is at https://harmonica.org.uk/llms.txt. Checks before
proposing changes: `uv run pytest -q`, `uv run ruff check src/harmonica tests`, and
`cd web && npm run build`.
