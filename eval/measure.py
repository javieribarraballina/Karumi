"""Real measurements for the pitch: every number here is computed, none is assumed.

    python -m eval.measure books https://books.toscrape.com
    python -m eval.measure internet https://the-internet.herokuapp.com

Writes the demo map to data/demo/<name>.json (screenshots in data/demo/<name>/shots)
and appends one row to eval/results.md.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from backend.atlas import graph, identify
from backend.atlas.explorer import explore

name, url = sys.argv[1], sys.argv[2]
out = Path("data/demo") / name
cache = Path(".cache/llm")
calls_before = len(list(cache.glob("*.json"))) if cache.exists() else 0

t = time.monotonic()
raw = explore(url, str(out))
m = graph.build_map(raw)
build_s = time.monotonic() - t
Path(f"data/demo/{name}.json").write_text(json.dumps(m, indent=2))
llm_calls = (len(list(cache.glob("*.json"))) if cache.exists() else 0) - calls_before

# Locate: FRESH screenshots at a different viewport (1024x768), scrolled 300px,
# not the images the map was built from.
fresh = out / "fresh"
fresh.mkdir(exist_ok=True)
top1 = top3 = n = 0
with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 1024, "height": 768})
    for s in m["screens"]:
        try:
            page.goto(s["url"], wait_until="domcontentloaded", timeout=15000)
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(300)
            shot = fresh / f"{s['id']}.png"
            page.screenshot(path=str(shot))
        except Exception:
            continue
        r = identify.locate(str(shot), m)
        n += 1
        top1 += r["screen_id"] == s["id"]
        top3 += s["id"] in [c["screen_id"] for c in r.get("candidates", [])[:3]]
    b.close()

# Paths: from the start screen to every other screen.
start = m["screens"][0]["id"]
targets = [s["id"] for s in m["screens"][1:]]
found = sum(graph.find_path(m, start, tid)["found"] for tid in targets)

row = (f"| {name} | {len(raw['pages'])} | {len(m['screens'])} | {top1}/{n} ({100*top1/max(n,1):.0f}%) "
       f"| {top3}/{n} ({100*top3/max(n,1):.0f}%) | {found}/{len(targets)} | {build_s:.0f}s | {llm_calls} |")
res = Path("eval/results.md")
if not res.exists() or "| site |" not in res.read_text():
    res.write_text("# Measured results (eval/measure.py)\n\n"
                   "| site | pages crawled | screens | locate top-1 (fresh 1024x768, scrolled) | locate top-3 "
                   "| paths found from start | crawl+map time | LLM calls |\n|---|---|---|---|---|---|---|---|\n")
with res.open("a") as f:
    f.write(row + "\n")
print(row)
