# Harmonica: Song Classification & Grouping Architecture

**Status:** DRAFT — agreed in discussion, pending owner approval. No code written yet.
**Date:** 2026-07-02. **Owner input:** `user-input-log.md` → 2026-07-02 "Classification architecture discussion".

This document records the agreed architecture for how songs are classified into weight groups,
sub-groups (covers), and cooldown tags — so a classification agent can be prompted correctly and the
result imported and verified. It is the design contract; the classification **prompt**, the **import**
path, and the **verification** checks are written against it once approved.

---

## 1. Why this exists

The prior import agent produced bad groupings. The canonical example: a weight group
`"Opportunity Rover / Space"` carried by **14 musically-unrelated songs** when only **1** is actually
about the Opportunity Rover. (The old Storage importer also split that one compound label on `/` into
two identical 14-member groups.) Measured smells in the current 250-song DB:

- `Nerdcore` and `Game Songs` each swallow **76 of 250 songs** (~30% of the library each).
- `Unknown / review` is the "artist" of **49 songs**.
- `sub_group` follows `"<group> :: <title>"`, so **233 of 250** are unique 1-member "families" — the
  cover machinery has nothing real to rank.

**Diagnosis (validated by a 5-agent research pass):** the *algorithm's math is sound and needs no
structural change.* Every failure above is a **truth-of-membership** failure — a label asserted for
songs it isn't true of — not a flaw in the weighting. The fix is a disciplined classifier plus a
data-layer truth check, **not** a group-size floor.

Key algorithmic fact that anchors everything: a song's base score is a share-weighted mean of
per-group terms `T(N) = (1 + β·ln N)/N` (β = 1.25), each ≤ 1, so **base ∈ (0, 1], maxed at 1.0 by an
all-singleton song.** Niche songs sit near 1.0, songs in crowded groups sit below. That per-song
elevation of small groups *is* the intended anti-domination behaviour — a 20-song group gets ~4.7×
a singleton's airtime, not 20×.

---

## 2. The three-axis facet model

Every song is described on three independent axes. Crucially, **tagging (what is true) is decoupled
from weighting (what earns a long-run weight group).** The agent tags everything true; only a capped
subset is promoted to weight groups. The rest persist as cooldown tags — nothing true is lost, but a
song can't buy airtime by accumulating labels.

| Axis | What it is | Becomes a weight group? | Budget |
|---|---|---|---|
| **Artist** | the genuine performing artist(s) | Always | 1+ artists, **shared slice** (§4) — separate from the aboutness budget |
| **Aboutness** | `topic` (source/franchise or literal subject: Minecraft, space, war) and `theme` (cross-work motif: villain songs, finales) | Up to **2** total | the "artist + up to 2" budget |
| **Mood** | upbeat, melancholic, hype… | **No, by default** — rides the cooldown-tag axis | promoted to a weight group only if the owner curates it |

Everything true beyond the promoted set (a 3rd theme, moods, descriptive traits) is recorded as a
**cooldown tag** (§5), which drives short-run variety but not long-run frequency.

---

## 3. The three-tier vocabulary

| Tier | Adds long-run airtime? | Spaces/clusters songs? | Shown in library browse? |
|---|---|---|---|
| **Visible weight group** | ✅ | ✅ (group cooldown) | ✅ |
| **Hidden weight group** | ✅ (novelty boost preserved) | ✅ | ❌ — only in the song's own detail |
| **Cooldown tag** | ❌ | ✅ (signed, §5) | ❌ |

**Hidden weight group** (new, additive `WeightGroup.hidden: bool`, default false): a *truthful*
one-off group that will realistically never grow (a genuinely unique subject with no broader home).
The algorithm **ignores `hidden` entirely** — the song keeps its novelty boost — but library-browse /
group-list surfaces filter `hidden = false`. The agent's test (owner's words): *"Could more songs
plausibly join this group in future?"* Yes → visible (Minecraft). No → hidden. Prefer routing a
would-be one-off into an existing/growable theme first; a one-off that's already covered by a real
theme is dropped, not hidden.

---

## 4. Artist handling — Option C (shared slice)

Collaborations are common in this library (`Black Gryph0n & Baasik` ×4, `A x B` credits, etc.), so
"exactly one artist" is wrong. Instead:

- **List every genuine performer** as its own artist weight group (so each accrues fair long-run
  credit and identity).
- The performers **share a single artist "slice"** — their memberships carry deterministic
  `share = (artist-slice)/N` values (via the existing `GroupMembership.share` field), so a song's
  **total weight is invariant to how many artists are credited.** A 3-way collab does not play ~8%
  more than the same song as a solo just for listing more names.
- A trivial `feat.` mention with no real performance may stay a **cooldown tag** instead of a full
  artist group.
- The **artist axis is separate from the ≤2 aboutness budget.** Collaborations expand the artist
  axis; they never spend a topic/theme slot.

This is the only option that both credits every collaborator *and* keeps airtime independent of the
length of the credits — consistent with the frequency-neutral principle below.

---

## 5. Cooldown tags — now signed (repel **or** attract)

A cooldown tag never changes how *much* a song plays; it changes *when*. It is now **bidirectional**:

- **Positive (repel, the classic case):** after a same-tag song plays, briefly dampen other same-tag
  songs so near-identical songs don't bunch up (`upbeat` after `upbeat`).
- **Negative (attract / affinity, new):** after a same-tag song plays, briefly *boost* linked songs
  so they **cluster** — e.g. two consecutive musical numbers that go better together. This is the
  concrete mechanism for the long-standing "clustering-encouraged" intent.

Implemented as a **signed strength** on the tag link (additive schema). All signed cooldown behaviour
is settings-controllable.

**Future extension (not now):** learned affinity — if a song consistently earns a higher rating when
it *follows* a specific other song, propose that pairing as a negative-cooldown/affinity link. Needs
rating-conditional-on-predecessor data; the signed-tag mechanism is what makes it expressible later.

---

## 6. Sub-groups & covers

Re-key `Track.sub_group` from the broken `"<group> :: <title>"` convention to a **per-composition work
key = the original rendition's `song_id`.**

- A **valid `sub_group`** requires **2+ true renditions of the same underlying composition** (cover,
  reprise, live/acoustic, remix, remaster, cast recording). Exactly one is flagged
  `is_original_rendition`. A song that is the sole rendition of its work gets `sub_group = NULL`.
- **Identity test:** *"Would hearing both back-to-back feel like the same song twice?"* Sharing a
  topic/theme/mood/artist is **not** a cover. Explicitly not covers: two songs about the same subject,
  a sample/interpolation, a medley/mashup (that's a new original work), two unrelated songs sharing a
  title.
- A **cover inherits the original's topic/theme weight groups** (copied `GroupMembership` rows) but
  keeps its **own performing-artist group** (aboutness travels with the composition; artist does not).
- Covers gain no extra long-run weight (only the logarithmic `L(n)` nudge when the feature is on).
- **Covers OFF (default):** non-original renditions are **hidden from algorithmic queues** (still
  browsable/playable on demand), so "off" means "this song has one canonical version." Cold-start
  coverage treats the **set (its original)** as the unit, so a hidden cover never demands a first-play
  it can't get.

---

## 7. Enforcement & reuse (additive data layer)

- **Reuse-before-create (mandatory):** before minting a group, match the candidate against a canonical
  registry (names + aliases + a normalised key: lowercase, strip diacritics/punctuation, drop leading
  articles, singularise, strip performer decorations). Reuse on hit. Normalisation only collapses
  spellings of the *same* concept — it never merges two distinct-but-correlated concepts (Meridian vs
  Marlowe Vance stay separate, per the owner's no-auto-merge decision).
- **Provenance/reason** column on each `GroupMembership`: *why* this song is in this group (a lyric,
  the source work, explicit metadata). Makes the truth test auditable at the data layer — where the
  Opportunity Rover bug actually lived.
- **The truth test (the single rule that prevents Opportunity Rover):** a non-artist membership of
  song *s* in group *g* is valid **only if** "Song *s* is [about / from the work / in the theme of] *g*"
  is literally true of *s* **judged in isolation**, with citable per-song evidence. Never propagate a
  label by association, co-occurrence, or playlist proximity. If the only reason *s* is in *g* is that
  some *other* song is in *g*, the membership is invalid. **No numeric size floor** — truthful
  singletons are welcome; lies are not.

---

## 8. The review ("Venn") artifact

Alongside the classification, the agent emits a **review map** for the owner to approve *before*
import: every group with its size and overlaps (which songs sit in intersections), plus auto-flagged
smells — a group whose members share no artist/source token, a song carrying 4+ groups, a `sub_group`
that's unique-per-song, an over-broad bucket. This is the safety net that catches the Opportunity
Rover class of error at review time. (Possible later: an in-app interactive Venn view — deferred.)

---

## 9. Import & verification

- **Import via the structured JSON API** (`POST /library/import-json`), whose payload has first-class
  `tracks[].groups[] = [{name, group_type, share}]`, `tracks[].sub_group`, and top-level `groups[]`.
  This path has **no delimiter-splitting**, so the `"A / B"` → two-groups bug class disappears. The
  old `weight_group_names` string parser is retired for this workflow.
- **Verification checks** (run after import): group sizes match the classification; no song exceeds
  artist-axis + 2 aboutness; rendition families have 2+ members and exactly one original; over-broad
  buckets are gone; spot-check individual songs via `GET /tracks/{id}`; and re-emit the review map
  **from the live DB** to confirm it matches what was approved.

---

## 10. Additive schema changes (all safe under `create_all`)

Agreed so far, no existing column altered:

- `WeightGroup.hidden: bool` (default false) — UI visibility only.
- Signed **strength** on the cooldown-tag link — enables negative/affinity tags.
- Per-song **artist `share`** values on `GroupMembership` (field already exists) — Option C.
- **Re-key** `Track.sub_group` to the original's `song_id`; populate `is_original_rendition`.
- Canonical **group registry / alias** table + membership **provenance** column.

**Optional (build only if warranted):** frequency-neutral anchor for singleton tags (behind a
setting — inert here, kept for generality); exclude non-original renditions from `group_sizes`
(removes a cover double-count); nullable `WeightGroup.parent_id` for correlated-group cooldown sharing
(only if Meridian/LMM double-suppression is ever felt); `Track.cover_of_track_id` FK (cleaner than the
string-key + bool convention).

---

## 11. Explicitly out of scope

- **Algorithm adapts to a learned utility function** — the owner already decided this isn't feasible
  (see 2026-07-02 settings entry). Not built.
- **DPP/MMR reranking** — overkill and opaque at 250 songs; the existing probabilistic weighting plus
  an optional deterministic anti-cluster post-filter is enough.
- **Anchoring on preset numbers** — the listening presets (Familiar/Balanced/Discovery/Long game) are
  being revised; the architecture must not depend on their current values.

---

## 12. Open questions (for owner approval)

1. **Over-broad groups.** `Nerdcore`/`Game Songs` (~76 songs each) and `Unknown / review` (artist ×49)
   are the same truth-test smell as Opportunity Rover, at scale. Dissolve/replace them with specific
   franchises + specific artists during the corrective pass? (Recommendation: **yes**.)
2. **Covers hidden while off.** Confirm non-original renditions are hidden from queues (not competing
   as separate songs) while the covers feature is off. (Recommendation: **yes**.)
3. **Agent autonomy.** Auto-assign artist + high-confidence proper-noun source/topic memberships, but
   route every newly-minted group and every fuzzy theme/mood-as-group to the review map for a quick
   yes/no? (Recommendation: **yes** — that's where false positives enter.)
4. **Corrective reclassify pass.** Run one idempotent pass that re-derives `GroupMembership`/`sub_group`
   via this rulebook and rewrites those rows (additive-safe, no migrations) — after snapshotting the
   DB? (Recommendation: **yes**.)
5. **One-off redundancy.** When a growable theme (Space) and a genuine one-off both apply, drop the
   one-off as redundant, or keep it as a hidden group for metadata? (Recommendation: **drop**.)
