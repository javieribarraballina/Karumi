# Measured results (eval/measure.py)

| site | pages crawled | screens | locate top-1 (fresh 1024x768, scrolled) | locate top-3 | paths found from start | crawl+map time | LLM calls |
|---|---|---|---|---|---|---|---|
| books | 12 | 6 | 1/6 (17%) | 3/6 (50%) | 5/5 | 17s | 0 |
| internet | 15 | 14 | 7/14 (50%) | 10/14 (71%) | 13/13 | 15s | 0 |

**Scale check** (explore at 40 pages / 300 s): the-internet 40 pages in 41 s; python.org 40 pages in 40 s. Both stop at the page cap, about 1 s per page. Map building takes under 2 s without an LLM; with labels, add about 1–2 s per screen.

**How to read this:** "locate" uses FRESH screenshots (1024×768 viewport, scrolled 300 px), not the images the map was built from, and image fingerprints only (no API key, 0 LLM calls). "Paths found" means `find_path` returns a route from the start screen; we do not replay clicks yet.
