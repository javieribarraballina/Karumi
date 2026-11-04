# Measured results (eval/measure.py)

Run by Juan on 2026-11-04 with **no API key**: screen recognition used image fingerprints only (no LLM fallback), labels come from page text.
"Where am I?" uses fresh screenshots at a different window size (1024x768, scrolled). Paths are found on the graph, not replayed in a browser.

| site | pages crawled | screens | locate top-1 (fresh 1024x768, scrolled) | locate top-3 | paths found from start | crawl+map time | LLM calls |
|---|---|---|---|---|---|---|---|
| books.toscrape.com | 12 | 6 | 1/6 (17%) | 3/6 (50%) | 5/5 | 15–17 s | 0 |
| the-internet.herokuapp.com | 15 | 14 | 7/14 (50%) | 10/14 (71%) | 13/13 | 15–17 s | 0 |

Not measured yet: the same runs with an API key (LLM fallback on), to compare "fingerprints alone" vs "with LLM".
