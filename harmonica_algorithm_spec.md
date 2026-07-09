# Harmonica: Weighted Local Music Playlist Algorithm Specification

## 1. Purpose

Harmonica is intended to be a local, open-source music library and playlist-generation app. Its main purpose is not simply to shuffle music, but to generate listening queues that reflect the user's real preferences while avoiding the common failure mode where one large group, such as a musical soundtrack, dominates the playlist.

The app should eventually:

- index a local music library;
- store user-curated metadata;
- generate weighted playlists;
- reduce repetition at song, group, and sub-group level;
- learn from user ratings over time;
- provide statistics about listening patterns and preferences;
- remain independent of Spotify, Apple Music, or any one downloader/player.

The minimum viable product should be a local script/app that reads local files and a metadata file, then writes an ordered playlist file such as `.m3u8` for VLC or another local player.

---

## 2. Original Idea

The original problem was:

> I like some music from musicals, but if I include those songs in a normal playlist, the playlist gets repetitive. For example, a 50-song playlist might contain 25 songs from the same musical.

The original proposed solution was to assign songs to groups such as:

- musical;
- artist;
- theme;
- source;
- mood;
- song family;
- cover/reprise family.

Then the app should give larger groups more chance of appearing, but not linearly. A group with 25 songs should not be 25 times as likely as a group with one song.

The preferred weighting shape was logarithmic:

\[
W(n)=1+\ln(n)
\]

This gives:

| Group size \(n\) | \(1+\ln(n)\) |
|---:|---:|
| 1 | 1.000 |
| 2 | 1.693 |
| 3 | 2.099 |
| 4 | 2.386 |
| 5 | 2.609 |
| 10 | 3.303 |
| 25 | 4.219 |
| 50 | 4.912 |

This is desirable because it is concave. Each extra song increases the group's chance, but by less than the previous extra song.

---

## 3. Criticisms and Design Corrections

### 3.1 Do not remove songs from the pool until the cycle resets

A first possible approach was to select songs without replacement. That was rejected.

If selected songs are removed from the pool, then a 50-song generated playlist can become distorted. The small groups may appear early, and the end of the playlist may become dominated by the large musical group that still has many unplayed songs left.

Conclusion: songs should remain eligible, but their probability should be heavily reduced immediately after being played and should gradually recover.

---

### 3.2 Do not use group-specific beta for taste preference

The logarithmic formula can include a global strength parameter:

\[
W_g=m_g(1+\beta\ln(N_g))
\]

Where:

- \(N_g\) is the number of songs in group \(g\);
- \(\beta\) controls how strongly group size matters;
- \(m_g\) is a group-specific taste multiplier.

The important distinction is:

- \(\beta\) controls the shape of the group-size curve;
- \(m_g\) controls how much the user likes or dislikes a specific group.

So, if a group should be twice as prominent, use:

\[
m_g=2
\]

Do not use a group-specific \(\beta\) for this. That would muddle the meaning of the parameters.

Recommended default:

\[
\beta=1.25
\]

Group multipliers can then be adjusted separately:

| Group preference | Suggested \(m_g\) |
|---|---:|
| Repetitive / annoying | 0.4 to 0.7 |
| Normal | 1.0 |
| Preferred | 1.2 to 1.5 |
| Very strongly preferred | 1.6 to 2.0 |

Avoid values above 2.0 unless the user explicitly wants a group to dominate.

---

### 3.3 Cooldown tags alone are not enough

A proposed solution was to use one primary group for long-run weighting and additional cooldown tags for short-run variety.

That solves short-run sequencing, for example:

> Do not play two songs from the same musical, same artist, or same version family too close together.

However, it does not fully solve long-run representation.

If a song genuinely belongs to several important categories, such as a musical, an artist, and a theme, it should be able to count towards all relevant long-run groups. Cooldown tags alone would only stop repetition; they would not give those overlapping groups proper long-run influence.

Conclusion: use **weight groups** for long-run probability and **cooldown tags** for short-run similarity.

---

### 3.4 Do not let descriptive metadata unfairly inflate or dilute a song

A song may have many descriptive tags:

```text
Meridian; musical; upbeat; ensemble; rap; Marlowe Vance; Act 1
```

It would be bad if every descriptive tag acted as a full weight group. Songs with richer metadata would become overpowered, or, if divided too harshly, over-penalised.

Conclusion:

- **weight groups** are curated categories that affect long-run representation;
- **cooldown tags** are descriptive labels that mainly affect short-run repetition;
- only weight groups count when splitting a song's probability contribution.

---

### 3.5 Do not make the rating front-end part of the MVP

A rating interface was considered: the app would play each song several times in random order and ask the user to rate it out of 10. This could be useful eventually, but it is too much friction for the first version.

Problems:

- ratings are affected by mood and context;
- rating every song three times is tedious;
- a complex rating UI delays the core algorithm;
- excessive rating influence would make the app overplay current favourites.

Conclusion: include support for ratings in the data model, but implement the rating UI later.

---

### 3.6 Do not build the app around Spotify or any one source

A third-party file source may be useful, but it should not be treated as the trusted foundation of the app.

Reasons:

- legal and terms-of-service uncertainty;
- security risk from third-party downloaders;
- possible metadata mismatch;
- fragility if upstream APIs or services change;
- musicals, covers, remasters, and cast recordings are particularly easy to misidentify.

Conclusion: Harmonica should be built around local files plus its own metadata file. File source should be interchangeable.

---

## 4. Final Algorithmic Model

### 4.1 Entities

#### Song

Each song should have:

```yaml
song_id: unique stable ID
file_path: local file path
title: song title
artist: display artist
album: display album
weight_groups: list of long-run groups
sub_groups: list of version/reprise/cover families
cooldown_tags: list of short-run similarity tags
song_multiplier: individual preference multiplier
ratings: optional multi-factor ratings
last_played_index: most recent play position, if any
```

#### Weight group

A weight group is a curated long-run category.

Examples:

```text
Meridian
The Ashen City
Undertide
Marlowe Vance
Villain songs
Dramatic finales
Standalone favourites
```

Each weight group should have:

```yaml
group_id: unique stable ID
name: display name
group_type: source | artist | theme | mood | other
group_multiplier: user preference multiplier
last_played_index: most recent play position for any song contributing through this group
```

#### Sub-group

A sub-group represents versions of essentially the same song.

Examples:

```text
Follow Me Down variants
One More Dawn variants
My Mark variants
Original + reprise pair
Studio + live version pair
```

Sub-groups should usually affect cooldown only. They should not create extra long-run weighting unless deliberately promoted to weight groups.

#### Cooldown tag

Cooldown tags are short-run similarity labels.

Examples:

```text
upbeat
slow ballad
ensemble
solo female vocal
Act 1
opening number
finale
comic song
```

Cooldown tags should not normally generate base probability. They should only reduce the chance of very similar songs appearing too close together.

---

## 5. Core Probability Formula

Each song belongs to one or more weight groups.

Let:

- \(s\) be a song;
- \(G_s\) be the set of weight groups containing song \(s\);
- \(k_s=|G_s|\), the number of weight groups containing song \(s\);
- \(q_{s,g}\) be song \(s\)'s membership share in group \(g\);
- \(N_g\) be the number of songs in group \(g\);
- \(m_g\) be the group multiplier;
- \(m_s\) be the song multiplier;
- \(\beta\) be the global logarithmic group-size strength.

For the MVP, use equal fractional membership:

\[
q_{s,g}=\frac{1}{k_s}
\]

Later, allow manual unequal shares, such as:

```yaml
weight_groups:
  Meridian: 0.7
  Marlowe Vance: 0.3
```

The base contribution from group \(g\) is:

\[
B_{s,g}=q_{s,g}\cdot \frac{m_g(1+\beta\ln(N_g))}{N_g}
\]

The base score for song \(s\) is:

\[
B_s=m_s\sum_{g\in G_s}B_{s,g}
\]

This means a song can appear in every relevant weight group, but its contribution is divided across those groups so it is not automatically favoured just because it has more labels.

---

## 6. Cooldowns

Cooldowns should be applied after the base score is calculated.

The final score is:

\[
S_s=B_s\cdot C_s\cdot C_{sub}\cdot C_{tag}
\]

Where:

- \(C_s\) is the song cooldown;
- \(C_{sub}\) is the sub-group/version-family cooldown;
- \(C_{tag}\) is the combined cooldown-tag penalty.

Group cooldown can either be applied inside the group contribution or as a later penalty. The cleaner method is to apply it inside each group contribution:

\[
B_{s,g}=q_{s,g}\cdot \frac{m_g(1+\beta\ln(N_g))}{N_g}\cdot C_g
\]

Then:

\[
B_s=m_s\sum_{g\in G_s}B_{s,g}
\]

This is better for overlapping groups because a song's contribution through a recently-played group can be reduced without necessarily destroying its contribution through all other groups.

---

### 6.1 Song cooldown

The user wanted a song to have zero or near-zero probability immediately after being played, then gradually recover until the full song-count horizon has passed.

Let:

- \(d_s\) be the number of songs since song \(s\) was last played;
- \(T\) be the total number of songs in the library;
- \(H_s=T\), the song recovery horizon.

Recommended simple linear recovery:

\[
C_s(d_s)=
\begin{cases}
0, & d_s=0\\
\frac{d_s}{H_s}, & 0<d_s<H_s\\
1, & d_s\ge H_s
\end{cases}
\]

If a song has never been played, set:

\[
C_s=1
\]

This gives:

| Songs since last play | Cooldown multiplier, if \(H_s=100\) |
|---:|---:|
| 0 | 0.00 |
| 10 | 0.10 |
| 25 | 0.25 |
| 50 | 0.50 |
| 100+ | 1.00 |

This avoids hard removal while still making immediate repeats practically impossible.

---

### 6.2 Group cooldown

Group cooldown prevents the same musical, artist, or theme appearing repeatedly in quick succession.

Let:

- \(d_g\) be the number of songs since group \(g\) last appeared;
- \(H_g\) be the group recovery horizon.

Recommended default:

\[
H_g=\min(G,12)
\]

where \(G\) is the number of active weight groups.

Use a non-zero floor so groups are discouraged rather than completely banned:

\[
C_g(d_g)=
\begin{cases}
\epsilon_g+(1-\epsilon_g)\frac{d_g}{H_g}, & d_g<H_g\\
1, & d_g\ge H_g
\end{cases}
\]

Recommended:

\[
\epsilon_g=0.05
\]

So a group can technically repeat, but it is heavily discouraged immediately after use.

---

### 6.3 Sub-group cooldown

Sub-groups handle covers, reprises, live versions, and variants of essentially the same song.

Example:

```text
Song: Follow Me Down
Sub-group: Follow Me Down variants
```

Sub-group cooldown should usually be stronger than general group cooldown, because hearing the original and then a reprise/cover soon afterwards often feels like a repeat.

Recommended:

\[
H_{sub}=\min(30,T)
\]

\[
\epsilon_{sub}=0.01
\]

Use:

\[
C_{sub}(d)=
\begin{cases}
\epsilon_{sub}+(1-\epsilon_{sub})\frac{d}{H_{sub}}, & d<H_{sub}\\
1, & d\ge H_{sub}
\end{cases}
\]

If the song has no sub-group, set:

\[
C_{sub}=1
\]

---

### 6.4 Cooldown tags

Cooldown tags are optional for the first version. They can improve short-run variety, but they should not be overused.

For each recently used tag, apply a small penalty. The combined tag penalty should be capped so a song is not crushed just because it shares several tags.

Example:

\[
C_{tag}=\max(0.25,\prod_i C_i)
\]

Recommended MVP decision: implement cooldown tags after the core weight-group and sub-group system works.

---

## 7. Song Ratings

Ratings should eventually be multi-dimensional rather than one single score.

Possible rating dimensions:

```text
lyrics
message
music/composition
performance/vocals
replayability
overall enjoyment
```

A possible weighted rating average:

\[
R_s=0.15L+0.15M+0.25C+0.15P+0.20Re+0.10O
\]

Where:

- \(L\) = lyrics;
- \(M\) = message;
- \(C\) = composition/music;
- \(P\) = performance;
- \(Re\) = replayability;
- \(O\) = overall enjoyment.

Map this to a modest song multiplier:

\[
m_s=0.5+\frac{R_s}{10}
\]

So:

| Rating \(R_s\) | Song multiplier \(m_s\) |
|---:|---:|
| 1 | 0.6 |
| 5 | 1.0 |
| 10 | 1.5 |

Do not allow ratings to create extreme multipliers early on. Otherwise the system will overplay current favourites and undermine the whole anti-repetition goal.

MVP recommendation:

```text
Set all song multipliers to 1.0.
Store optional rating fields in the metadata.
Implement the rating UI later.
```

---

## 8. Selection Procedure

For each next song:

1. Load all songs and metadata.
2. For each weight group, calculate group size \(N_g\).
3. For each song, calculate base contribution across all its weight groups.
4. Apply song cooldown.
5. Apply sub-group cooldown.
6. Apply optional tag cooldown.
7. Convert all positive scores into probabilities.
8. Randomly select one song using weighted random selection.
9. Append the song to the generated playlist.
10. Update virtual play history.
11. Repeat until the target playlist length is reached.

Probability calculation:

\[
P(s)=\frac{S_s}{\sum_j S_j}
\]

If all scores are zero because the library is tiny or cooldowns are too aggressive, fall back to:

```text
ignore group/sub-group cooldowns first;
then ignore song cooldown only if absolutely necessary.
```

---

## 9. Pseudocode

```python
import math
import random


def linear_recovery(distance, horizon, floor=0.0):
    if distance is None:
        return 1.0
    if distance <= 0:
        return floor
    if distance >= horizon:
        return 1.0
    return floor + (1.0 - floor) * (distance / horizon)


def weighted_choice(items, weights):
    total = sum(weights)
    if total <= 0:
        return random.choice(items)
    return random.choices(items, weights=weights, k=1)[0]


def generate_playlist(songs, groups, length, beta=1.25):
    """
    songs: list of song objects/dicts.
    groups: dict keyed by group_id.
    length: number of tracks to generate.
    beta: global logarithmic group-size strength.
    """

    output = []
    current_index = 0
    total_songs = len(songs)

    # group size: raw number of songs belonging to each weight group
    group_sizes = {group_id: 0 for group_id in groups}
    for song in songs:
        for group_id in song["weight_groups"]:
            group_sizes[group_id] += 1

    for _ in range(length):
        scores = []

        for song in songs:
            song_multiplier = song.get("song_multiplier", 1.0)
            weight_groups = song["weight_groups"]
            k = len(weight_groups)

            if k == 0:
                # Fallback: a song with no group behaves like its own singleton group.
                base_score = song_multiplier
            else:
                base_score = 0.0

                for group_id in weight_groups:
                    group = groups[group_id]
                    N_g = max(1, group_sizes[group_id])
                    m_g = group.get("group_multiplier", 1.0)

                    group_weight = m_g * (1.0 + beta * math.log(N_g))
                    within_group_share = group_weight / N_g
                    membership_share = 1.0 / k

                    d_g = None
                    if group.get("last_played_index") is not None:
                        d_g = current_index - group["last_played_index"]

                    H_g = min(len(groups), 12)
                    C_g = linear_recovery(d_g, H_g, floor=0.05)

                    base_score += membership_share * within_group_share * C_g

                base_score *= song_multiplier

            d_s = None
            if song.get("last_played_index") is not None:
                d_s = current_index - song["last_played_index"]

            C_s = linear_recovery(d_s, total_songs, floor=0.0)

            # Sub-group cooldown.
            C_sub = 1.0
            sub_group = song.get("sub_group")
            if sub_group:
                last_sub = song.get("last_sub_group_played_index")
                d_sub = None if last_sub is None else current_index - last_sub
                H_sub = min(30, total_songs)
                C_sub = linear_recovery(d_sub, H_sub, floor=0.01)

            final_score = base_score * C_s * C_sub
            scores.append(max(0.0, final_score))

        chosen = weighted_choice(songs, scores)
        output.append(chosen)

        # Update virtual play history.
        chosen["last_played_index"] = current_index

        for group_id in chosen.get("weight_groups", []):
            groups[group_id]["last_played_index"] = current_index

        chosen_sub = chosen.get("sub_group")
        if chosen_sub:
            for song in songs:
                if song.get("sub_group") == chosen_sub:
                    song["last_sub_group_played_index"] = current_index

        current_index += 1

    return output
```

This pseudocode is not final production code. It is meant to fix the algorithmic structure before implementation details are added.

---

## 10. Suggested Metadata Format

### CSV version

```csv
song_id,file_path,title,artist,album,weight_groups,sub_group,cooldown_tags,group_notes,song_multiplier
meridian_my_mark_001,/Music/Meridian/My Mark.flac,My Mark,Meridian Original Cast,Meridian,"Meridian;Marlowe Vance",My Mark variants,"rap;musical;ensemble;upbeat",,1.0
ashen_city_one_more_dawn_001,/Music/The Ashen City/One More Dawn.flac,One More Dawn,Ashen City Original Cast,The Ashen City,"The Ashen City;dramatic finale",One More Dawn variants,"ensemble;finale;musical",,1.0
standalone_001,/Music/Other/Song.flac,Song,Artist,Album,"Standalone",,"pop;slow",,1.0
```

CSV is easy to edit manually, but nested ratings and unequal membership shares are awkward.

### JSON version

```json
{
  "songs": [
    {
      "song_id": "meridian_my_mark_001",
      "file_path": "/Music/Meridian/My Mark.flac",
      "title": "My Mark",
      "artist": "Meridian Original Cast",
      "album": "Meridian",
      "weight_groups": {
        "Meridian": 0.5,
        "Marlowe Vance": 0.5
      },
      "sub_group": "My Mark variants",
      "cooldown_tags": ["rap", "musical", "ensemble", "upbeat"],
      "song_multiplier": 1.0,
      "ratings": {
        "lyrics": null,
        "message": null,
        "music": null,
        "performance": null,
        "replayability": null,
        "overall": null
      }
    }
  ],
  "groups": {
    "Meridian": {
      "group_type": "source",
      "group_multiplier": 0.8
    },
    "Marlowe Vance": {
      "group_type": "artist",
      "group_multiplier": 1.0
    }
  }
}
```

JSON is better for the long run because it can store custom group shares, ratings, and app state more cleanly.

Recommendation:

```text
Use CSV for the first throwaway prototype.
Move to JSON or SQLite once the algorithm feels correct.
```

---

## 11. Local Playback Implementation

The recommended MVP flow is:

```text
Local music files -> metadata file -> Harmonica generator -> output.m3u8 -> VLC with shuffle off
```

The generated `.m3u8` file should contain ordered local file paths:

```m3u
#EXTM3U
/Music/Meridian/My Mark.flac
/Music/The Ashen City/One More Dawn.flac
/Music/Other/Song.flac
```

Important: do not use VLC shuffle. Harmonica should generate the order. VLC should only play it.

---

## 12. iPhone Implementation Options

iPhone support should not be the first implementation target.

Possible approaches later:

1. Generate playlists on the computer, then transfer local files and playlists to VLC on iOS.
2. Store music on a local server/NAS and stream generated playlists to the iPhone.
3. Build a native iOS app that imports local files, stores metadata, generates queues, and plays audio itself.

Best long-run option: native iOS app.

Best MVP option: local desktop playlist generator.

---

## 13. Recommended MVP Scope

Implement only:

- local file inventory;
- manually edited metadata;
- weight groups;
- group multipliers;
- logarithmic group weighting;
- fractional membership across overlapping weight groups;
- song cooldown;
- group cooldown;
- sub-group cooldown;
- `.m3u8` playlist export.

Do not implement yet:

- rating UI;
- automatic recommendation/discovery;
- iPhone app;
- complex visual statistics;
- automatic metadata inference;
- Spotify/Apple Music integration;
- third-party source dependency;
- advanced cooldown-tag logic.

---

## 14. Recommended Defaults

```yaml
beta: 1.25
song_recovery_horizon: total number of songs in library
group_recovery_horizon: min(number_of_weight_groups, 12)
group_cooldown_floor: 0.05
sub_group_recovery_horizon: min(30, total number of songs)
sub_group_cooldown_floor: 0.01
default_group_multiplier: 1.0
default_song_multiplier: 1.0
playlist_generation_length: 100 to 200 songs
```

---

## 15. Testing the Algorithm

Before building a UI, test the algorithm using simulated libraries.

### Test 1: One large musical plus many singletons

Library:

```text
25 Meridian songs
25 standalone songs
```

Expected behaviour:

- Meridian should appear more than any one standalone group;
- Meridian should not be 50% of the generated playlist unless deliberately boosted;
- Meridian songs should not cluster heavily.

---

### Test 2: Overlapping groups

Library:

```text
Song A: Meridian + Marlowe Vance
Song B: Meridian only
Song C: Marlowe Vance only
Song D: Standalone only
```

Expected behaviour:

- Song A should not become overpowered merely because it has two groups;
- both Meridian and Marlowe Vance should still have long-run influence.

---

### Test 3: Covers and reprises

Library:

```text
Original song
Reprise
Cover
Live version
```

Expected behaviour:

- these should not appear too close together;
- they should not create a large artificial weight merely by being many versions of essentially the same song.

---

### Test 4: Cooldown recovery

Expected behaviour:

- immediately after playing, a song has zero or near-zero probability;
- halfway through the recovery horizon, it has roughly half its normal probability;
- after the full horizon, it has normal probability again.

---

## 16. Main Conclusion

The final algorithm should be:

\[
S_s=C_s\cdot C_{sub}\cdot C_{tag}\cdot m_s\sum_{g\in G_s}
\left(
q_{s,g}\cdot \frac{m_g(1+\beta\ln(N_g))}{N_g}\cdot C_g
\right)
\]

Then select each next song with probability:

\[
P(s)=\frac{S_s}{\sum_j S_j}
\]

This preserves the main requirements:

- bigger groups get more weight, but sublinearly;
- one-song groups still have meaningful probability;
- musicals do not dominate purely by size;
- overlapping groups are handled without simple double-counting;
- songs are not removed from the pool;
- recently played songs and groups gradually recover;
- covers and reprises can be controlled through sub-group cooldowns;
- ratings can later become song multipliers;
- local-file playback remains the foundation.

