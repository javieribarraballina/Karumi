# Atlas: 3-minute pitch

Karumi × Comillas · Track 1 · Javier, Juan, Blanca, Nacho, Andrés

| Time | Speaker | Part |
|---|---|---|
| 0:00–0:30 | Javier | What we built |
| 0:30–1:15 | Juan + Nacho | Live demo |
| 1:15–1:50 | Andrés | What it proves |
| 1:50–2:30 | Blanca | Weakest part |
| 2:30–3:00 | Javier | One more week |

## Javier: what we built (0:00–0:30)
"A demo agent lands on an app it has never seen. Before it can show anything, it needs to know where it is and how to get somewhere. We built Atlas. Give it a URL: it explores the app on its own, groups pages into screens and builds a map. Screens are nodes, clicks are edges. Then it answers two questions: where am I, and how do I get to X?"

## Juan + Nacho: live demo (0:30–1:15)
**Juan:** "My explorer opens the site in a headless browser and follows same-site links. It visits at most two pages per URL pattern, so a shop with a thousand books costs two visits, not a thousand."

**Nacho** (live, using the precomputed map and a screenshot tested beforehand): "This is the-internet.herokuapp.com, mapped in about fifteen seconds. I upload a screenshot it hasn't seen, and it highlights the screen. Now I ask for Checkboxes: here are the clicks, step by step."

## Andrés: what it proves (1:15–1:50)
"We measured on two public sites, with fresh screenshots at a different window size, and without an API key:
- Mapping: 12 pages became 6 screens on books.toscrape, and 15 became 14 on the-internet, in 15 to 17 seconds.
- Paths found from the start screen: 5 of 5 and 13 of 13.
- Where am I: 50% top-1 and 71% top-3 on the-internet; 17% and 50% on books."

## Blanca: weakest part (1:50–2:30)
"Our weakest part is recognising pages that share a layout. Every book page looks the same, so image fingerprints alone get only 17% right. Atlas needs the vision model to tell them apart, and we measured without it. Merging was the other trap: plain white pages all look alike, so two pages now merge only if they look alike and their text matches. Atlas also doesn't log in, and single-page apps that never change URL aren't explored."

## Javier: one more week (2:30–3:00)
"With one more week: measure with the vision model on, explore behind a login with a test account, click buttons as well as links for single-page apps, and confirm each path by replaying its clicks. That is the map Karumi's agent needs before its first demo."
