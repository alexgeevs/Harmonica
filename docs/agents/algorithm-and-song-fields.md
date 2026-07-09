# How the Algorithm Works, and What Each Song's Fields Should Be

A working summary for agents preparing a library. The full mathematical treatment is in
`harmonica_algorithm_spec.md` at the repository root. How to produce and import a classification
payload is in `song-classification-prompt.md` and `classification-import-and-verify.md` beside
this file. This document explains just enough of the algorithm that the fields you fill in make
sense, because every field exists to feed a specific part of it.

## The algorithm in one page

Each queue slot is a weighted draw over the whole library. A song's weight is a product of
factors:

1. **Group weight (β).** Songs belong to weight groups (artist, source/franchise, theme). Larger
   groups count for more, but sublinearly (`size^β`), so a 100-song source does not drown a
   10-song one. Group membership can carry a share, so a song split between two artists does not
   count fully for both.
2. **Ratings.** Star ratings become multipliers between a floor and a ceiling. Ratings are
   normalised first: marks from an unusually harsh or generous sitting are reverted towards the
   mean, and repeat marks average over time.
3. **Cooldowns.** After a play, the song, its groups, and its sub-group are suppressed and
   recover gradually. This is the anti-repetition core: it acts at three levels, so neither one
   song, one franchise, nor one rendition family monopolises a session.
4. **History and skips.** A skip within the first tenth of a song is a strong negative signal.
   Under half is a weaker one with partial repeat credit. Completion is full repeat credit.
5. **Satiation and rediscovery.** Heavy recent play of a song rests it before the listener tires
   of it. Well-rated songs untouched for months regain weight and resurface.
6. **Cold start.** Unheard and unrated songs get a boost until the library has fair coverage.
7. **Visual priority and clustering.** Tracks with video are favoured when the user watches
   rather than listens, and a clustering bias makes same-group runs more or less likely.

## The fields, and what to base them on

The structured import format is one folder per song containing the media file(s) plus a
`song_config.json`. The fields the importer reads:

| Field | Feeds | What it should be based on |
| --- | --- | --- |
| `track_id` | Identity | A stable unique id (the folder name is used if absent). Never reuse one; imports de-duplicate on it. |
| `song_title_guess` / `original_title` | Display | The song's title. The first non-empty one wins. |
| `original_artist_names` | Display, grouping | The performing artist(s) as commonly credited. |
| `weight_group_names` | Group weight, group cooldowns | The song's artist, source/franchise, and theme memberships. This is the field the algorithm leans on hardest. Groups should be broad enough to be meaningful (a group of one does nothing) and narrow enough to be honest (do not tag half the library "favourites"). |
| `version_family_name` | Sub-group cooldown, cover families | The family a rendition belongs to when several versions of one song exist (covers, dubs, reprises, live cuts). All versions of one song share one family name; the family then competes as a single unit and the cover-selection feature picks among its members. Leave it out for songs with a single version. |

Media in the folder is linked automatically: video and audio assets are recognised by extension,
and re-imports reconcile assets without touching curation.

Beyond the import file, these per-track fields exist in the API (`PATCH /tracks/{id}`) and matter
to the algorithm: `has_lyrics`, `audio_only`, `is_original_rendition` (the reference version in a
cover family), `manual_multiplier` (a hand override on the song's weight), cooldown tags (shared
cooldown across songs that are not a group, e.g. two songs sampling the same melody), and clip
bounds.

## Practical guidance for classification

- Reuse existing group names from `GET /library/export-json` before inventing new ones. Merging
  duplicate groups later is manual work for the user.
- When a song legitimately belongs to several groups, list them all; shares can split the
  membership so the song is not over-weighted.
- Be conservative with `version_family_name`: two songs that merely sound similar are not a
  family. A family is the same underlying song.
- After importing, run `scripts/verify_classification.py` to catch over-broad groups, over-tagged
  songs, and invalid families before the user listens on top of a bad classification.
