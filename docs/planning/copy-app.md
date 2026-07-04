# App UI copy (edit in place)

Edit the text under each heading; leave the headings themselves alone, they say where each
string lives so the edits can be applied back to `web/src/App.tsx`, `web/src/presets.ts` and
`web/src/CurateView.tsx`.

---

## App.tsx — sidebar strapline

Your library, sequenced by expected utility rather than at random.

## App.tsx — backend unreachable error

Could not reach the Harmonica backend. It may not be running.

## App.tsx — now-playing placeholder (mini player)

Generate a queue to start listening

## App.tsx — now-playing placeholder (main player subtitle)

Harmonica will put together your next listening session.

## App.tsx — empty queue, line 1

Your queue is empty

## App.tsx — empty queue, line 2

Generate a session and it will appear here, ready to reorder, trim, and play.

## App.tsx — tag tooltip for tracks without media

Media not available yet

## App.tsx — cover comparison, stop-preview button

Stop and return to this version

## App.tsx — cover comparison, verdict confirmation

Your preference has been recorded.

## App.tsx — saved sessions, empty state

Saved sessions will appear here.

## App.tsx — stats, nothing played yet

Nothing played yet. Generate a queue and press play.

## App.tsx — break modal, heading

Time for a short break

## App.tsx — break modal, body

Playback is paused: that was two heavily compressed (lossy) tracks in a row. Over-compressed music appears to be genuinely more fatiguing; in one lab study it caused lasting ear damage in guinea pigs that the same energy of ordinary music did not.

## App.tsx — break modal, Economist link text

Read The Economist on this →

## App.tsx — break modal, button

Resume playback

## App.tsx — break modal, footnote

You can soften or turn this off in Settings → Hearing health.

## App.tsx — settings section note: Recommendation core

How strongly groups and your ratings shape the queue.

## App.tsx — settings section note: Anti-repetition & variety

How quickly a just-played song, group, or variant is allowed back.

## App.tsx — settings section note: History & feedback

How your plays and skips steer the next session.

## App.tsx — settings section note: Coverage (cold start)

Making sure every song gets a fair first hearing.

## App.tsx — settings section note: visual priority

Giving priority to tracks with video when you are watching rather than merely listening.

## App.tsx — settings section note: hearing health

Moderating loudness and listening fatigue, in line with the WHO's safe-listening guidance.

## App.tsx — settings section note: Rating normalisation

How repeat ratings are averaged and normalised before they steer the queue.

## App.tsx — settings section note: Repetition & rediscovery

Avoid wearing a song out by over-playing it, and bring back dormant favourites.

## App.tsx — settings section note: "why this song" panel

How much detail the “why this song” panel shows while you listen.

## App.tsx — settings section note: cover selection

When a song has several renditions, let the queue pick which one to play. Off by default — turn it on if your library has covers.

## App.tsx — presets intro

A preset sets every control below; you can still fine-tune afterwards.

## App.tsx — presets, custom-mix line

Custom mix: adjust any control, or pick a preset to start afresh.

## App.tsx — "How settings apply" note

Changes affect the next queue you generate. Existing sessions keep the snapshot they were built with, so tweaking won't disturb what you're hearing now.

## App.tsx — profile panel, local-mode note

Currently local: the full library, with global settings.

## App.tsx — profile banner, empty-library suffix

It's empty; import or scan songs to fill it (duplicates reuse the shared file).

## App.tsx — new-profile hint

New profiles capture your current settings as their snapshot.

## App.tsx — track editor, rating hint

Each tap adds a rating; the shown value is your running average.

## App.tsx — library, no matching tracks

No tracks match this view.

## App.tsx — library, no track selected

Select a track to edit details and ratings.

---

## presets.ts — Familiar, tagline

Comfort & favourites

## presets.ts — Familiar, description

Leans towards what you already love: favourites replay sooner and similar songs stay together, in the manner of a streaming service.

## presets.ts — Balanced, tagline

The default blend

## presets.ts — Balanced, description

Harmonica's sensible default: rewards what you rate highly while steadily cooling down anything you've heard recently.

## presets.ts — Discovery, tagline

Give everything a chance

## presets.ts — Discovery, description

Brings unheard and unrated tracks forward and stops large groups dominating, so the whole library gets fair coverage. Useful while you are still rating things.

## presets.ts — Long game, tagline

Never wear a song out

## presets.ts — Long game, description

Maximises long-term utility by penalising repetition heavily: a song you have just heard is strongly held back, and variety across artists and sources is enforced.

---

## CurateView.tsx — intro paragraph

Hand your library to a curation agent, then bring its proposal back here. You'll see every change and approve them one by one; nothing is written until you apply.

## CurateView.tsx — no differences found

No differences found; your library already matches this file.

## CurateView.tsx — nothing to review

Nothing to review; the proposal matches your library.

## CurateView.tsx — paste placeholder

…or paste the proposed library JSON
