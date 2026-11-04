# Atlas: 3-minute pitch

Karumi × Comillas, Track 1: How does it learn to find its way around the app?
Team: Javier, Juan, Blanca, Nacho, Andrés. Structure and speakers by Andrés; every number comes from `eval/results.md`.

| Time | Speaker | Part |
|---|---|---|
| 0:00–0:30 | Javier | 1. What we built |
| 0:30–1:15 | Juan + Nacho | Live demo |
| 1:15–1:55 | Andrés | 2. What it proves |
| 1:55–2:30 | Blanca | 3. Weakest part |
| 2:30–3:00 | Javier | 4. One more week |

---

### 1. What we built (Javier, 30 s)
> "An AI agent that has to demo a product it has never seen needs a map first. We built **Atlas**. You give it one URL. With no training and no manual setup, it explores the app, groups pages into distinct screens, and builds a graph of how to get from one screen to another. It answers the agent's two questions: *where am I?* and *how do I get to X?*"

### Live demo (Juan + Nacho, 45 s)
*(Nacho has the UI open on the `internet` map.)*
> **Juan:** "The explorer opens the site in a headless browser, follows only safe same-site links (never logout or delete), and caps itself at two pages per URL pattern so it maps 15 kinds of page instead of 1,000 product pages."
>
> **Nacho:** "Here is the map it built. I upload a fresh screenshot to *Where am I?* *(upload)* and it highlights the screen. Now *Take me to Checkboxes* *(type)*: here is the click-by-click route." *(If there's time: click Explore on a new URL and show the progress counter.)*

### 2. What it proves (Andrés, 40 s)
> "Measured today on two public sites, using fresh screenshots at a different window size and scrolled, not the images we built the map from:
> - Crawl plus map in **15–17 seconds**; at scale, **40 pages in 40 seconds** on python.org.
> - A route was found to **every screen it discovered: 13 of 13 and 5 of 5**.
> - With image fingerprints alone, *Where am I?* gets the right screen first **50%** of the time on the-internet and is in the top three **71%** of the time. On the bookstore, where every page looks alike, only **17%**.
> That last number is why the LLM fallback exists."

### 3. Weakest part (Blanca, 35 s)
> "Our weakest part is recognising screens that share a template. Fingerprints can't tell one book page from a category page. The vision-LLM fallback is built for that, but we haven't measured it yet. Second, we don't explore behind a login or inside single-page apps whose URL never changes. Third, we find routes but don't yet replay the clicks to prove they work."

### 4. One more week (Javier, 30 s)
> "With one more week: (1) measure and tune the LLM fallback, then replace it with a small fine-tuned screen classifier for speed and cost; (2) replay every route in a real browser to verify it; (3) logged-in exploration and a map that updates itself when the app changes. Atlas gives a demo agent what a new employee gets on day one: a map. Thank you."

---

## Q&A cheat sheet
- **Infinite loops?** *Juan:* Visited-URL set, URL normalisation, 2 pages per pattern, page and time budget (15 pages / 90 s live, 40 / 300 for demo maps).
- **Why fingerprints plus an LLM?** *Blanca:* Fingerprints are instant and free, and work when screens look different (50% top-1 on the-internet). The LLM is the fallback for ambiguous matches. We haven't measured that path yet.
- **Value for Karumi?** *Andrés:* Instead of a person scripting each customer's demo, the agent lands on the customer's app and knows how to reach every feature within a minute.
- **How did AI help ship it?** Every module was built with Claude and Codex agents in parallel, against a shared contract, and Codex reviewed each branch before merge (it caught invented eval numbers and a destructive-link bug).
