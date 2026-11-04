# Atlas: an agent that maps an app it has never seen

Karumi × Comillas hackathon, **Track 1: How does it learn to find its way around the app?**

Paste a URL. Atlas explores the app on its own, works out which screens exist, and builds a map: screens are nodes, the click that links two screens is an edge. Then:

- **Where am I?** Upload a screenshot and Atlas says which screen it is.
- **How do I get to X?** Atlas returns the click-by-click path.

This covers all three Track 1 examples (screen recognition, screenshots to map, autonomous exploration) in one demo.

---

## Team and ownership

Each person owns one folder. **Only edit your own folder.** That is what stops merge conflicts. If you need a change in someone else's folder, ask them.

| Person | Role | Owns | Delivers |
|---|---|---|---|
| **Javier** | Lead: graph, API, integration | `backend/atlas/graph.py`, `backend/atlas/api.py`, `backend/atlas/llm.py`, `schema` section below | `build_map()`, `find_path()`, the FastAPI server, merges |
| **Juan** | Explorer | `backend/atlas/explorer.py` | `explore()`: crawls a URL, returns raw pages + transitions |
| **Blanca** | Screen identifier | `backend/atlas/identify.py` | `cluster_pages()`, `label_screen()`, `locate()` |
| **Nacho** | Frontend | `frontend/` | The clickable demo UI |
| **Andrés** | Eval, deploy, pitch | `eval/`, `Dockerfile`, `pitch.md` | Accuracy numbers, a live link, the 3-minute pitch |

Roles can be swapped. The ownership rule cannot.

---

## Time budget

The hackathon runs 12:30–14:00 and it is already past 13:00, so we have about **60 minutes**. Adjust the clock times if yours differ.

| When | Goal |
|---|---|
| **by 13:10** | Javier commits the skeleton, `schema`, and `data/sample_map.json`. Everyone clones, installs, and runs the "hello" check below. |
| 13:10–13:35 | Everyone builds their piece against the sample data. **Do not wait for anyone else.** |
| 13:35–13:45 | Integrate end to end on one easy site. |
| 13:45–13:52 | Andrés's eval numbers go into the pitch. Deploy. Fix only what is broken. |
| **13:52** | **Code freeze.** Nothing new after this. |
| 13:52–14:00 | Rehearse the pitch twice with the live link. |

**MVP first.** An ugly map of 8 screens that works beats a beautiful crawler that doesn't finish. Cut list if we run late, in order: login-gated screens, modals, scroll states, fancy graph styling.

---

## Stack

- **Backend:** Python 3.11+, FastAPI, Playwright (Chromium), Pillow + `imagehash`, `pytest`.
- **Frontend:** plain HTML + JS served by FastAPI (no Node, no build step). Graph drawing with Cytoscape.js from a CDN.
- **LLMs:** Claude for vision labeling (`claude-sonnet-5-5` for quality, `claude-haiku-5-5` for cheap bulk calls). Any vision-capable OpenAI model also works. All model calls go through **one** wrapper, `backend/atlas/llm.py` (Javier), which reads `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` from the environment and **caches every response on disk**. Never commit keys.

### Repo layout

```
Karumi/
  README.md                # this file
  requirements.txt
  backend/atlas/
    __init__.py
    llm.py                 # Javier: one place for model calls + disk cache
    explorer.py            # Juan
    identify.py            # Blanca
    graph.py               # Javier
    api.py                 # Javier
  frontend/                # Nacho
    index.html  app.js  style.css
  eval/                    # Andrés
    ground_truth/  run_eval.py  results.md
  data/
    sample_map.json        # fake map everyone builds against
    demo/                  # precomputed maps for the live demo (Andrés + Javier)
  tests/                   # each person adds test_<their_module>.py
  Dockerfile               # Andrés
  pitch.md                 # Andrés
```

### Setup (everyone, 5 minutes)

```bash
git clone https://github.com/javieribarraballina/Karumi.git && cd Karumi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
export ANTHROPIC_API_KEY=...   # ask Javier / the team channel, never commit
pytest -q                      # should pass on the skeleton
```

`requirements.txt` (Javier commits it): `fastapi uvicorn[standard] playwright pillow imagehash pytest httpx python-multipart anthropic openai`

---

## The contract (read this before writing any code)

Everything connects through these shapes. Change them only by telling **everyone**.

### 1. Raw crawl: Explorer → Identifier + Graph

```json
{
  "app": "https://books.toscrape.com",
  "pages": [
    {
      "id": "p1",
      "url": "https://books.toscrape.com/",
      "title": "All products | Books to Scrape",
      "screenshot": "data/runs/<run>/shots/p1.png",
      "text": "first ~2000 chars of visible text",
      "links": [{"text": "Travel", "href": "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"}]
    }
  ],
  "transitions": [
    {"from": "p1", "to": "p2", "action": "click 'Travel'"}
  ]
}
```

### 2. Map: Graph → API → Frontend (the final product)

```json
{
  "app": "https://books.toscrape.com",
  "screens": [
    {
      "id": "s1",
      "label": "Home / product list",
      "summary": "Grid of books with a category sidebar.",
      "url": "https://books.toscrape.com/",
      "screenshot": "data/runs/<run>/shots/p1.png",
      "phash": "c3d2e1f0a1b2c3d4",
      "page_ids": ["p1", "p7"]
    }
  ],
  "edges": [
    {"from": "s1", "to": "s2", "action": "click 'Travel'"}
  ]
}
```

`screens` are the **deduplicated** pages: many raw pages (`page_ids`) can be one screen (e.g. every book detail page is one "Product detail" screen). Deciding that is Blanca's job and the heart of the project.

### 3. Function signatures

```python
# explorer.py (Juan)
def explore(url: str, out_dir: str, max_pages: int = 15, max_seconds: int = 90) -> dict:
    """Returns the Raw crawl dict above; also writes <out_dir>/raw.json and shots/*.png"""

# identify.py (Blanca)
def cluster_pages(pages: list[dict]) -> list[list[str]]:
    """Group page ids that are the same screen. Returns e.g. [["p1","p7"], ["p2"]]"""
def label_screen(screenshot_path: str, text: str) -> dict:
    """Returns {"label": str, "summary": str}"""
def locate(screenshot_path: str, map: dict) -> dict:
    """Returns {"screen_id": "s3", "confidence": 0.0-1.0, "candidates": [{"screen_id","score"}, ...top 3]}"""

# graph.py (Javier)
def build_map(raw: dict) -> dict:
    """Calls cluster_pages + label_screen, merges transitions into edges, returns the Map dict"""
def find_path(map: dict, start_id: str, target: str) -> dict:
    """target is a screen id OR free text ('checkout'). Returns {"found": bool, "steps": [{"from","to","action"}], "target_id": str}"""
```

### 4. HTTP API (Javier)

| Method | Route | Does |
|---|---|---|
| POST | `/api/explore` body `{"url": "..."}` | Starts a job, returns `{"job_id": "..."}` |
| GET | `/api/jobs/{job_id}` | `{"status": "running\|done\|error", "progress": "7/15 pages", "map_id": "..."}` |
| GET | `/api/maps` | List available maps (includes precomputed `data/demo/*`) |
| GET | `/api/maps/{map_id}` | The Map JSON |
| POST | `/api/maps/{map_id}/locate` multipart `file` | The `locate()` result |
| GET | `/api/maps/{map_id}/path?from=s1&to=checkout` | The `find_path()` result |
| GET | `/shots/...` | Static screenshots |

Frontend and eval can start from `data/sample_map.json` today, before any of this works.

---

## Javier: Lead, graph, API, integration

**Goal:** turn raw crawls into a map, answer path queries, serve everything over HTTP, and keep the team unblocked.

### Do first (by 13:10, the whole team is waiting on this)
1. Create the repo layout above with empty modules that raise `NotImplementedError` and stub returns.
2. Commit `requirements.txt` and `data/sample_map.json` (a hand-made map of 6 screens and 7 edges, with real placeholder screenshots; make a few 400×300 PNGs with Pillow). Push to `main`.
3. Message the team: "skeleton is up, pull."

### Then build
1. **`llm.py`:** `ask(prompt, image_path=None, model="haiku") -> str`. Hash the (prompt, image bytes, model) and cache to `.cache/llm/<hash>.json`. Retry once on failure. This will save us when the API rate-limits during the demo.
2. **`graph.py`:**
   - `build_map`: call `cluster_pages`, then `label_screen` on one representative page per cluster, compute screen ids, and map every transition's page ids to screen ids. Drop self-loops and duplicate edges.
   - `find_path`: BFS over edges. If `target` isn't a screen id, ask the LLM (text only, via `llm.ask`) to pick the best matching screen label, or use simple fuzzy matching on labels first and fall back to the LLM.
3. **`api.py`:** the routes above. Run `explore` in a background thread and store job status in a dict. Mount `frontend/` at `/` and `data/` at `/shots` (or similar).
4. **Integration:** from 13:35, run the full pipeline on 1 site and tell each person exactly what broke in their module.

### Tests (`tests/test_graph.py`)
- `build_map` on a hand-built raw dict with stubbed `cluster_pages`/`label_screen` (use `monkeypatch`) gives the expected screens and edges, with no self-loops or duplicates.
- `find_path` returns the shortest path on `sample_map.json`, `found=False` for an unreachable screen, and handles `start == target`.
- API: `TestClient` hits `/api/maps/sample` and gets 200 with valid JSON.

### Recommendations
- Stub the LLM in tests so `pytest` runs offline and fast.
- Return clear error messages from the API; the frontend shows them verbatim during the demo.
- Pre-run the explorer on the demo sites yourself and save the maps in `data/demo/` so the demo survives bad wifi.
- Merge small and often. Rebase onto `main` before merging.

---

## Juan: Explorer

**Goal:** given a URL, autonomously visit the app and capture what's needed to build a map. Fast and bounded.

### Build
1. Playwright sync API, headless Chromium, viewport 1280×800. Open the URL, wait for `networkidle` (with a timeout), save a full-viewport screenshot to `<out_dir>/shots/<id>.png`.
2. For each page, collect: final URL, title, ~2000 chars of `inner_text("body")`, and links (visible `<a href>` plus buttons, with text and href). Resolve relative hrefs.
3. **Exploration strategy (start simple):** BFS from the start URL, **same-origin only**. Skip `mailto:`, `tel:`, file downloads, `#` anchors, and logout/delete-like links.
4. **Don't crawl 500 product pages.** Normalize URLs by replacing digit/slug segments with placeholders (`/book/123` → `/book/{n}`) and visit only **2 pages per URL pattern**. This is the key trick that keeps the crawl small and diverse.
5. Respect the budget: stop at `max_pages` or `max_seconds`. Print progress (`7/15`) so Javier's API can show it.
6. Record a transition for every followed link: `{"from": page_id, "to": page_id, "action": "click '<link text>'"}`.
7. Write `<out_dir>/raw.json` in the contract shape.

### Stretch (only if the basic crawl is solid)
- Click JS buttons and menus that don't change the URL (single-page apps), then record the new state as a page.
- Let an LLM choose which 5 links look most important (nav, pricing, login, dashboard) instead of plain BFS.

### Tests (`tests/test_explorer.py`)
- Run a local `http.server` over a tiny 4-page HTML folder in a fixture; `explore()` returns 4 pages, correct transitions, and screenshots that exist on disk.
- `max_pages=2` really stops at 2.
- External links and `mailto:` are not followed.
- URL-pattern limiter: 10 links of the form `/item/1`…`/item/10` produce at most 2 visited pages.
- Manual check on 2 real sites (below): it finishes under the time budget and doesn't crash.

### Recommendations
- Test sites that are built for scraping and won't ban us: `https://books.toscrape.com`, `https://quotes.toscrape.com`, `https://the-internet.herokuapp.com`. Also try one real marketing site, since that is what the judges care about.
- Wrap each page visit in try/except; one bad page must not kill the run.
- Use `page.wait_for_load_state("domcontentloaded")` plus a short extra wait rather than always waiting for `networkidle`, which hangs on sites with analytics.
- Close the browser in a `finally`.

---

## Blanca: Screen identifier

**Goal:** decide which pages are the same screen, name each screen, and recognize a screen from a screenshot. This is what the judges will remember.

### Build
1. **`cluster_pages(pages)`:**
   - Compute a perceptual hash (`imagehash.phash`) of each screenshot and a normalized URL pattern (digits and long slugs replaced).
   - Two pages are the same screen if their URL patterns match **or** their phash distance is small (start with ≤ 10; tune it using Andrés's ground truth).
   - Use union-find so grouping is transitive. Return lists of page ids.
2. **`label_screen(screenshot_path, text)`:** send the screenshot plus the page text to a vision model via `llm.ask` with a prompt like: *"This is a screen from a web app. Reply as JSON: `{"label": <3-5 word screen name>, "summary": <one sentence: what the user can do here>}`."* Parse the JSON defensively (strip code fences, fall back to the page title).
3. **`locate(screenshot_path, map)`:**
   - Stage 1: phash the uploaded image, compare against each screen's `phash`, take the top 3 candidates, and convert distance to a 0–1 score.
   - Stage 2: if the best score is low or the top two are close, send the upload plus the candidates' labels and summaries (and their thumbnails if cheap) to the vision model: *"Which of these screens is the image? Reply with the id and a confidence."*
   - Return `screen_id`, `confidence`, and the top 3 `candidates`.

### Tests (`tests/test_identify.py`)
- `cluster_pages` merges two pages with the same URL pattern and different content, and keeps two visually different pages apart (use small generated PNGs).
- `label_screen` with a stubbed `llm.ask` returns the parsed dict; with garbage model output it falls back without raising.
- `locate`: take a screenshot from `sample_map.json`, resize it to 80% and re-save as JPEG, and assert it still resolves to the same screen. This simulates a user's screenshot at a different size.
- Report top-1 accuracy over all sample screens in the test output.

### Recommendations
- phash alone will fail on pages that share a template (all product pages look alike). That's good for clustering, bad for locating. Stage 2 exists for that reason.
- Use the cheap model (`haiku`) for labeling many screens and the stronger one only for the locate fallback.
- Keep a threshold dict at the top of the file so Andrés can tune values without hunting through code.
- Be honest in the pitch about where this fails (see Pitch).

---

## Nacho: Frontend

**Goal:** a single page a judge can use in 10 seconds without explanation. No Node, no build step.

### Build (`frontend/index.html`, `app.js`, `style.css`)
1. **Top bar:** URL input + "Explore" button, plus a dropdown of ready-made maps from `GET /api/maps` (so the demo can start instantly).
2. **Graph:** Cytoscape.js (`<script src="https://unpkg.com/cytoscape/dist/cytoscape.min.js">`). Nodes show the screen label and its screenshot as the node background; edges show the action text. Clicking a node opens a side panel with the large screenshot, the summary, and the URL.
3. **"Where am I?" panel:** drag-and-drop or file input for a screenshot → `POST /api/maps/{id}/locate` → highlight the returned node, and show the confidence and the top 3 candidates.
4. **"How do I get to…" box:** a text input (or click a node) → `GET .../path` → highlight the path nodes and edges and list the steps ("1. Click 'Travel' → 2. …").
5. **Progress:** after Explore, poll `/api/jobs/{id}` every second and show the `progress` string, then load the map.
6. **Errors:** show the API's error message in a visible banner. Never fail silently.

### Start today against the sample
Hard-code `fetch("/data/sample_map.json")` until Javier's API is live, then switch to the real routes. Keep the API base URL in one constant.

### Tests (manual checklist, run before the freeze)
- [ ] Loads with the API down → shows a clear message, not a blank page.
- [ ] Select a ready-made map → graph renders, nodes show screenshots.
- [ ] Upload a screenshot → correct node highlights.
- [ ] Ask for a path → steps listed, path highlighted; unreachable target shows "no path".
- [ ] Works in Chrome at 1440 px and on a 1280×720 projector resolution.
- [ ] A 25-node map stays readable (layout `cose` or `breadthfirst`).

### Recommendations
- The demo must look good from 3 meters away: large fonts, high contrast, minimal chrome.
- Use a layout that doesn't overlap nodes (`breadthfirst` from the home screen reads like a sitemap).
- Add a "Load demo" button that picks a precomputed map and pre-fills a sample path query, so the pitch never depends on typing.

---

## Andrés: Eval, deploy, pitch

**Goal:** give us numbers to defend the project, a link judges can click, and a pitch that fits 3 minutes. Judges score "it works", "real-world value", and "what it proves", and you own all three.

### 1. Ground truth (start now, by 13:30)
For 2–3 sites (`books.toscrape.com`, `the-internet.herokuapp.com`, one real marketing site), open them yourself and write `eval/ground_truth/<site>.json`:

```json
{
  "app": "https://books.toscrape.com",
  "screens": ["Home", "Category listing", "Product detail", "Basket"],
  "url_to_screen": {"/": "Home", "/catalogue/category/": "Category listing"},
  "paths": [{"from": "Home", "to": "Product detail", "expected_clicks": 2}]
}
```

10–15 hand-labeled screens per site is plenty.

### 2. `eval/run_eval.py`
Runs `explore` → `build_map` on each site and prints a table to `eval/results.md`:

| Metric | How |
|---|---|
| **Coverage** | Share of ground-truth screens that Atlas found |
| **Dedupe quality** | Screens found vs. true screens (over-split / under-split) |
| **Locate accuracy** | For each ground-truth screen, take a **fresh** screenshot at a different viewport (e.g. 1024×768, and a scrolled state), call `locate`, and check top-1 and top-3 |
| **Path success** | For N queries, run `find_path`, then replay the steps in Playwright and check you arrive at the right screen |
| **Cost and time** | Seconds and number of LLM calls per site |

### 3. Deploy: the "if we can't click it, it doesn't count" rule
- Primary: a `Dockerfile` based on `mcr.microsoft.com/playwright/python` that runs `uvicorn backend.atlas.api:app --host 0.0.0.0 --port $PORT`. Deploy to Render or Railway.
- Fallback (set up **now**, not at the end): run locally and expose with `cloudflared tunnel --url http://localhost:8000` or ngrok. A laptop works too, per the rules.
- Make sure the precomputed maps in `data/demo/` load without any API key, so the link works even if a live crawl or an LLM call fails.

### 4. Pitch (`pitch.md`): 3 minutes, in this order
1. **What we built (30 s):** Atlas explores an unseen app and gives an agent a map. Live: pick the demo map, upload a screenshot, ask for a path.
2. **What it proves (45 s):** your real numbers from `results.md`. "Right screen X% of the time across N sites; path replay worked Y of Z times."
3. **Weakest part (45 s):** be specific and honest. Likely: screens behind login, single-page apps where the URL never changes, template-heavy pages that look identical. Judges reward knowing your limits.
4. **One more week (30 s):** authenticated exploration, a map that updates when the app changes, a small fine-tuned classifier replacing the LLM fallback for speed and cost.
5. **Buffer (30 s).**

Assign who talks for each part, then rehearse twice with the live link.

### Tests
- `run_eval.py` runs end to end on the sample map with stubs (`--offline` flag) so you can develop it before the real pipeline works.
- Open the deployed link from a **phone on mobile data** to prove it works outside our wifi.

### Recommendations
- Report numbers even when they're bad. "62% top-1, and here is why" beats a vague claim.
- Capture a 30–60 s screen recording of a successful run now. If everything breaks live, that is the backup.
- Keep the results table to 4–5 numbers. The slide must be readable in 3 seconds.

---

## Git workflow

1. `main` always works. Javier merges.
2. One branch per person: `git checkout -b juan/explorer`.
3. Commit and push every ~15 minutes: `git add <your files> && git commit -m "explorer: crawl + screenshots" && git push -u origin juan/explorer`.
4. Before asking for a merge: `git fetch && git rebase origin/main && pytest -q`.
5. Never commit: API keys, `.venv`, `.cache`, `data/runs/` (large). Add them to `.gitignore` (Javier, in the skeleton). Screenshots under `data/demo/` are the exception.
6. If you're stuck for more than 5 minutes, say so in the group chat. Stubbing your dependency is always allowed.

## Using AI tools (T3, Claude, ChatGPT)

Each person can paste a prompt like this into their own agent thread:

> I'm **<name>**, working on role **<role>** in the repo `javieribarraballina/Karumi`. Read `README.md`, specifically the contract and my section. Build exactly what my section lists, only inside the folders I own, and write the tests it asks for. Stub anything that depends on someone else's module using `data/sample_map.json`. Run `pytest -q` and report the results. Do not change the contract without telling me.

Good practice: ask the agent to write the tests **first**, ask it to run them, and have a second model (Claude if Codex wrote it, or the reverse) review the diff before you merge.

## Definition of done (for the freeze at 13:52)

- [ ] Live link (or laptop) opens the UI with at least 2 precomputed maps.
- [ ] Explore on a **new** URL works at least on the easy site.
- [ ] "Where am I?" and "Path" both work in the UI.
- [ ] `eval/results.md` has real numbers.
- [ ] Pitch rehearsed twice, with a backup recording.
