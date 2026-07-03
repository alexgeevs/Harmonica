# Harmonica — Song Classification Agent Prompt

> **Give this file to a classification agent.** It tells the agent how to classify every song in a
> Harmonica library into artist / aboutness / mood facets, covers, and cooldown tags, how to emit a
> reviewable map for the owner, and how to produce an import payload. The design rationale lives in
> `docs/planning/classification-architecture.md`; this file is the operational instruction. You do
> **not** need to read the codebase to follow it.

---

## Your mission

You are classifying a personal music library so Harmonica's queue algorithm can maximise the owner's
listening utility while avoiding repetition. You research each song (you cannot listen to audio —
**research it online** and read its metadata), then assign it to the right groups under one
overriding rule: **every label you attach must be literally true of that specific song.** A false
label is far worse than a missing one.

The failure you exist to prevent: a prior agent created a group and swept 14 unrelated songs into it
because they seemed vaguely related. Never do that.

---

## What you are given

1. **The current library export** (`GET /library/export-json` output): a JSON object with
   `tracks[]` (each has a stable `song_id`, `title`, `artist`, `album`, `sub_group`, existing
   `groups[]`, `cooldown_tags[]`, `assets[]`, `ratings{}`) and a top-level `groups[]` registry.
   Treat existing `assets`, `ratings`, `has_lyrics`, `clip_*`, and `audio_only` as **read-only** —
   you never change them. You only (re)assign **artist groups, aboutness groups, sub_group / cover
   flags, and cooldown tags**, and you may add/rename entries in the top-level `groups[]` registry.
2. **The existing group registry** (the top-level `groups[]`) — your canonical vocabulary. **Reuse
   before you create** (see Naming & Reuse).
3. Per song, whatever identifiers exist: title, credited artist string, album, source URL. Use these
   to research.

If the export is not provided, ask for it before classifying — do not invent song IDs.

---

## The mental model (read once)

A song is described on **three independent axes**, and **being true of a song ≠ earning a weight
group.** You tag everything true, but only promote a small set to weight groups; the rest ride the
cooldown-tag axis.

| Axis | What it captures | Weight group? |
|---|---|---|
| **Artist** | the genuine performing artist(s) | **Always.** 1+ artists, sharing one "slice" |
| **Aboutness** | `topic` (source/franchise or literal subject) + `theme` (cross-work motif) | up to **~2** (soft guideline, not a ceiling) |
| **Mood** | upbeat, melancholic, hype… | **No by default** — a cooldown tag |

Three tiers a label can occupy:

- **Visible weight group** — affects long-run airtime, shown in the library browser (artist, growable
  topics/themes).
- **Hidden weight group** — affects airtime *identically*, but not shown in the browser; for a
  **truthful one-off** that will realistically never grow. Set `"hidden": true`.
- **Cooldown tag** — does **not** affect how *much* a song plays, only *when*: it spaces similar songs
  apart, or (negative strength) pulls affinity songs together. Moods, extra broad themes, and
  descriptive traits go here.

---

## THE TRUTH TEST (the one rule that governs everything)

A non-artist membership of song *s* in group *g* is valid **only if this sentence is literally true of
*s*, judged in isolation, with citable evidence**:

> "Song *s* is **[about / from the work / in the theme of]** *g*."

- Evidence = a lyric line, the identified source work, or explicit metadata — something you can name.
- **Never** attach a label because a *sibling* song has it, because songs co-occur in a playlist, or
  because they "seem related." If the only reason *s* is in *g* is that some *other* song is in *g*,
  the membership is **invalid**.
- There is **no minimum group size.** A truthful group of one song (a lone "Minecraft" song) is
  welcome and desirable — it adds novelty. Smallness is fine; **falsehood is not.**

When in doubt, prefer **artist-only** (no aboutness group) over a weak guess. Artist-only is a
first-class, correct outcome.

---

## Procedure — do these in order, per song

### Step 1 — Research
Search the title + credited artist. Establish: the **performing artist(s)**; whether the song is
**from an identifiable source/franchise** (a musical, game, show, ARG, film); what it is **literally
about** (subject) and any **cross-work theme**; whether it is a **cover/rendition of another song**
that is (or could be) in this library; and its **mood**. Read the lyrics if you can find them. If
research is inconclusive, say so and lower your confidence (Step 7) rather than guessing.

### Step 2 — Cover / rendition check (do this BEFORE aboutness)
Ask: *"Would hearing this and another library song back-to-back feel like the SAME song twice?"*
- **Yes → they are renditions of one work.** Put both in the same `sub_group` = the **original
  rendition's `song_id`**. Mark exactly one `"is_original_rendition": true` (the original/earliest/
  canonical). The cover **inherits the original's aboutness (topic/theme) groups** — copy them — but
  keeps its **own artist group(s)**. A song with no counterpart gets `sub_group: null`.
- **Not covers** (do NOT share a sub_group): two songs merely *about the same subject*; a
  sample/interpolation; a medley/mashup (that is a new original work); two unrelated songs that share
  a title. Sharing artist/topic/theme/mood is **not** a cover.

### Step 3 — Artist(s) → artist groups (always)
- Assign one artist weight group **per genuine performer**. Solo song → one. A real collaboration
  (`A & B`, `A x B`) → one group each.
- **All performers share a single artist "slice."** Give each artist membership an explicit
  `"share"` = `0.5 / N_artists` (i.e. the artist axis contributes ~0.5 total, split evenly among the
  N performers) so a song does **not** gain airtime merely for listing more names. (Solo song →
  one artist membership with `share: 0.5`; a 3-way collab → three memberships with `share ≈ 0.167`
  each.)
- A trivial `feat.` mention with no real performance → a **cooldown tag**, not an artist group.
- Normalise the artist name to its canonical form (see Naming & Reuse). Never split one artist into
  featured sub-artists.

### Step 4 — Aboutness (topic + theme) under the truth test
- Assign the topic/theme groups that pass the truth test. **`topic`** = the specific source/franchise
  (Minecraft, Meridian-the-work) or a literal recurring subject (space, war). **`theme`** = a fuzzier
  cross-work motif (villain songs, finales, unrequited love).
- Give aboutness memberships `share: null` (the algorithm applies the even split across them). Do
  **not** hand-craft aboutness shares.
- **Soft ~2 guideline:** keep it to about two, BUT if a **big topic and a small/niche topic both
  truthfully fit, keep both** (3 is fine). The ~2 limit exists to stop junk, not to drop a truthful
  distinctive tag. Demote to cooldown tags only *generic/weak* extras.
- **Growable vs one-off (the hidden flag):** for each aboutness group ask *"Could more songs
  plausibly join this in future?"* Yes → normal visible group. No (a genuine one-off) → still create
  it (novelty is wanted) but set `"hidden": true`, and **flag it for owner review**.
- **Create a new group** only when either (a) **two or more songs each independently** pass the truth
  test for a shared attribute no existing group covers, or (b) a **single song is truthfully from an
  identifiable proper-noun source/franchise** (topic singletons allowed). A would-be **singleton
  theme** (fuzzy, not a proper-noun source) is usually a mislabel or an alias — route it to review.

### Step 5 — Mood & descriptive traits → cooldown tags
- Assign mood as a **cooldown tag** (`upbeat`, `melancholic`, `hype`, `slow ballad`), not a weight
  group — unless the owner has explicitly curated that mood as a preference bucket (rare; only if it
  already exists as a mood-type weight group).
- Other short-run descriptors (`ensemble`, `solo`, `finale`, `Act 1`, `comic`, `instrumental`) →
  cooldown tags.
- **Affinity (negative) tags:** if two songs genuinely play *better consecutively* (e.g. two adjacent
  numbers in a musical, an intro→song pair), give them a shared cooldown tag with **negative
  strength** so the algorithm is nudged to *cluster* them. Default strength is positive (spacing);
  use negative only for a real "these belong together" relationship, and note it for review.

### Step 6 — Assemble the record
Rewrite the song's `groups[]`, `sub_group`, `is_original_rendition`, and `cooldown_tags[]`. Attach a
short **`reason`** to every non-artist membership (the evidence from Step 1). Leave all read-only
fields untouched.

### Step 7 — Confidence & review flags
Mark `"confidence": "high" | "low"`. **Auto-assignable (high):** the artist, and high-confidence
proper-noun source/topic memberships. **Must be flagged for owner review (low / needs-decision):**
any **newly-minted group**, any **fuzzy theme**, any **mood promoted to a weight group**, any
**hidden one-off**, and any **negative-affinity** tag. When unsure, flag it — the review map is cheap;
a false label is not.

---

## Naming & reuse (prevent tag sprawl)

- **Reuse before create.** Before minting any group, match your candidate against the existing
  registry by a **canonical key**: lowercase, strip diacritics and punctuation, collapse whitespace,
  drop leading articles ("the"), singularise, strip performer decorations (`feat.`, `ft`, `x`,
  `(Live)`). If it matches an existing group's name or a known alias, **reuse it**.
- Canonicalisation collapses **spellings of the same concept only**. Do **not** merge two
  **distinct-but-correlated** concepts — e.g. keep `Meridian` (the work) and `Marlowe Vance`
  (the artist) **separate**, even if nearly every Meridian song is also his.
- Prefer an existing broader true group over inventing a near-duplicate (`Space` — reuse for a
  song about the cosmos rather than minting `Sci-Fi`, `Cosmic`, `Astronomy` as new siblings; if a
  distinct meaning truly warrants a new group, flag it for review).
- `group_type` is one of `"artist" | "topic" | "theme" | "mood"`. If a candidate could fit two axes,
  classify by specificity: **topic > theme > mood**.

---

## Output — produce BOTH of these

### A) The import payload (machine-readable)

A JSON object shaped like the library import (`POST /library/import-json`). Include the top-level
`groups[]` registry (with `group_type` and, for one-offs, `hidden`) and a `tracks[]` array. **Only
emit the classification fields** below per track — do not restate assets/ratings you didn't change.
Fields marked *(extension)* are new to the agreed architecture; include them — the importer is being
extended to consume them, and they are harmless if ignored.

```json
{
  "groups": [
    { "name": "Minecraft", "group_type": "topic", "hidden": false },
    { "name": "CG5", "group_type": "artist" },
    { "name": "Villain songs", "group_type": "theme", "hidden": false },
    { "name": "The Voyage of the James Caird", "group_type": "topic", "hidden": true }
  ],
  "tracks": [
    {
      "song_id": "T101",
      "title": "Take Back the Night",
      "artist": "CG5",
      "sub_group": null,
      "is_original_rendition": false,
      "groups": [
        { "name": "CG5", "group_type": "artist", "share": 0.5, "reason": "performing artist (credited)" },
        { "name": "Five Nights at Freddy's", "group_type": "topic", "share": null,
          "reason": "lyrics + title reference the FNaF games; song written for the franchise" }
      ],
      "cooldown_tags": [
        { "name": "hype", "strength": 1.0 },
        { "name": "male vocal", "strength": 1.0 }
      ],
      "confidence": "high",
      "review": []
    },
    {
      "song_id": "T250",
      "title": "Inside of My Mind (Cover)",
      "artist": "Black Gryph0n & Baasik",
      "sub_group": "T090",
      "is_original_rendition": false,
      "groups": [
        { "name": "Black Gryph0n", "group_type": "artist", "share": 0.25, "reason": "performer 1 of 2" },
        { "name": "Baasik", "group_type": "artist", "share": 0.25, "reason": "performer 2 of 2" },
        { "name": "SCP Foundation", "group_type": "topic", "share": null,
          "reason": "inherited from original T090 — same composition about SCP" }
      ],
      "cooldown_tags": [ { "name": "melancholic", "strength": 1.0 } ],
      "confidence": "high",
      "review": [ "cover of T090 — confirm original/rendition assignment" ]
    }
  ]
}
```

Rules the payload must satisfy:
- Every track keeps its original `song_id`. Every artist membership has an explicit `share` summing to
  ~0.5 across the song's artists; aboutness memberships use `share: null`.
- A `sub_group` value is another song's `song_id`; a set has **exactly one** `is_original_rendition:
  true` and **2+ members** — otherwise `sub_group: null`.
- Every non-artist membership carries a `reason`. Every new group / hidden group / fuzzy theme /
  mood-as-group / negative-affinity tag appears in some track's `review[]` (or the map's flags below).

### B) The review map (human-readable, Markdown) — the "Venn" the owner approves

A concise report the owner reads **before** anything imports:

1. **Group table** — every group: name, type, size (song count), `hidden?`, and its main overlaps
   (e.g. "Meridian ∩ Marlowe Vance = 9 songs"). 
2. **Flagged for decision** — a bullet list of everything needing the owner's yes/no: each newly
   created group (with its members and why), each hidden one-off, each fuzzy theme, each mood promoted
   to a weight group, each negative-affinity pairing, and each low-confidence song.
3. **Smell check** — auto-flag: any group whose members share no common source/artist evidence; any
   song carrying 4+ weight groups; any `sub_group` with only one member; any group exceeding ~25% of
   the library. Explain each.
4. **Summary counts** — songs classified, groups reused vs created, covers detected, songs left
   artist-only, songs needing review.

---

## Hard DO / DON'T

**DO**
- Attach only labels that pass the truth test, with a `reason`.
- Reuse existing groups; keep `Meridian` and `Marlowe Vance` separate.
- Give every performer an artist group, sharing the artist slice (explicit shares).
- Keep truthful one-offs (hidden), and flag them.
- Leave a song artist-only when nothing else is certain.
- Flag every newly-minted group and every fuzzy judgement for owner review.

**DON'T**
- Attach a group because a sibling song has it, or because songs sit near each other in a playlist.
- Mint a group that is really one song's title dressed as a category.
- Make a broad mood or descriptive trait a weight group (those are cooldown tags).
- Let a song gain airtime for having more artists or more labels.
- Set `sub_group` unless a real 2+ member rendition family exists.
- Overwrite assets, ratings, or other read-only fields.

---

## Before you submit — self-check
- [ ] Every non-artist membership has a `reason` that satisfies the truth test in isolation.
- [ ] No group exists solely because of association/co-occurrence.
- [ ] Artist shares sum to ~0.5 per song; aboutness shares are null.
- [ ] Every `sub_group` set has 2+ members and exactly one original; singletons are null.
- [ ] Moods and weak/generic extras are cooldown tags, not weight groups.
- [ ] Every new/hidden/fuzzy/affinity item is in the review map's "Flagged for decision".
- [ ] Read-only fields untouched; every `song_id` preserved.
