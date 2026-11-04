"""Screen identifier (Blanca).

Decides which crawled pages are the same screen, names each screen, and
recognises a screen from a new screenshot.

Public API (see README "The contract"):
    cluster_pages(pages)                 -> [["p1", "p7"], ["p2"], ...]
    label_screen(screenshot_path, text)  -> {"label": str, "summary": str}
    locate(screenshot_path, map)         -> {"screen_id", "confidence", "candidates", "method"}

Helpers other modules may use:
    screen_phash(path) -> hex str | None   (graph.py can fill screens[i]["phash"] with it)
    url_pattern(url)   -> str
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

# Tunable values in one place (Andrés can tune these against the ground truth).
THRESHOLDS = {
    "phash_same_screen": 10,   # max Hamming distance (of 64 bits) to treat two pages as one screen
    "phash_score_span": 32,    # distance at which the phash score drops to 0 (32 ≈ unrelated images)
    "locate_confident": 0.80,  # phash score above which we trust phash without asking the LLM
    "locate_margin": 0.10,     # ...and the gap needed between the 1st and 2nd candidate
    "slug_min_len": 25,        # path segments at least this long count as slugs
    "llm_max_candidates": 8,   # screens shown to the LLM in the locate fallback
}

LABEL_MODEL = "haiku"     # cheap model for labelling many screens
LOCATE_MODEL = "sonnet"   # stronger model only for the ambiguous locate fallback


# --------------------------------------------------------------------------- LLM
def _ask(prompt: str, image_path: str | None = None, model: str = "haiku") -> str:
    """Single entry point to Javier's wrapper. Imported lazily so this module
    works (with fallbacks) even before llm.py exists. Tests monkeypatch this."""
    from . import llm  # noqa: WPS433 (Javier's module)

    return llm.ask(prompt, image_path=image_path, model=model)


def _parse_json(text: str):
    """Parse JSON from a model reply: strips code fences, takes the outermost {...}."""
    if not isinstance(text, str):
        raise ValueError("not text")
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in reply")
        return json.loads(t[start : end + 1])


# ----------------------------------------------------------------------- hashing
def screen_phash(path: str | None) -> str | None:
    """Perceptual hash of an image as a 16-char hex string, or None if unreadable."""
    if not path:
        return None
    try:
        import imagehash
        from PIL import Image

        with Image.open(path) as im:
            return str(imagehash.phash(im.convert("RGB")))
    except Exception:
        return None


def _hamming(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


def _score(distance: int | None) -> float:
    if distance is None:
        return 0.0
    return round(max(0.0, 1.0 - distance / THRESHOLDS["phash_score_span"]), 3)


# ---------------------------------------------------------------- url patterns
_DIGITS = re.compile(r"^\d+$")
_INDEX = {"index.html", "index.htm", "index.php", ""}


def url_pattern(url: str) -> str:
    """Normalise a URL so pages built from the same template share a pattern.

    /catalogue/a-light-in-the-attic_1000/index.html -> host/catalogue/{slug}
    /book/123                                       -> host/book/{n}
    /catalogue/page-2.html                          -> host/catalogue/{slug}.html
    Query strings and fragments are ignored.
    """
    parts = urlsplit(url or "")
    segs = [s for s in parts.path.split("/")]
    out = []
    for seg in segs:
        if seg.lower() in _INDEX:
            continue
        stem, dot, ext = seg.rpartition(".") if "." in seg else (seg, "", "")
        if not dot:
            stem, ext = seg, ""
        if _DIGITS.match(stem):
            norm = "{n}"
        elif any(c.isdigit() for c in stem) or len(stem) >= THRESHOLDS["slug_min_len"]:
            norm = "{slug}"
        else:
            norm = stem.lower()
        out.append(norm + (dot + ext.lower() if dot else ""))
    return (parts.netloc.lower() + "/" + "/".join(out)).rstrip("/") or "/"


# --------------------------------------------------------------- cluster_pages
def cluster_pages(pages: list[dict]) -> list[list[str]]:
    """Group page ids that are the same screen.

    Two pages are the same screen if their URL patterns match OR their
    screenshots' perceptual hashes are within THRESHOLDS["phash_same_screen"].
    Union-find keeps the grouping transitive. Output order follows the crawl.
    """
    ids = [p["id"] for p in pages]
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            # keep the earliest-crawled page as root so output order is stable
            if ids.index(ra) < ids.index(rb):
                parent[rb] = ra
            else:
                parent[ra] = rb

    patterns = {p["id"]: url_pattern(p.get("url", "")) for p in pages}
    hashes = {p["id"]: p.get("phash") or screen_phash(p.get("screenshot")) for p in pages}

    by_pattern: dict[str, str] = {}
    for pid in ids:
        pat = patterns[pid]
        if pat in by_pattern:
            union(by_pattern[pat], pid)
        else:
            by_pattern[pat] = pid

    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            d = _hamming(hashes[a], hashes[b])
            if d is not None and d <= THRESHOLDS["phash_same_screen"]:
                union(a, b)

    groups: dict[str, list[str]] = {}
    for pid in ids:
        groups.setdefault(find(pid), []).append(pid)
    return list(groups.values())


# ---------------------------------------------------------------- label_screen
_LABEL_PROMPT = """This is a screenshot of one screen from a web app. Visible text (may be cut):
---
{text}
---
Name the screen the way a product person would (e.g. "Product detail", "Checkout", "Account settings").
Reply with ONLY JSON: {{"label": "<3-5 word screen name>", "summary": "<one sentence: what the user can do here>"}}"""


def _fallback_label(text: str) -> dict:
    first = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    label = first[:40] or "Unnamed screen"
    return {"label": label, "summary": ""}


def label_screen(screenshot_path: str, text: str) -> dict:
    """Ask the vision model for a short name and one-line summary. Never raises."""
    try:
        reply = _ask(_LABEL_PROMPT.format(text=(text or "")[:1500]), image_path=screenshot_path, model=LABEL_MODEL)
        data = _parse_json(reply)
        label = str(data.get("label", "")).strip()
        if not label:
            raise ValueError("empty label")
        return {"label": label[:60], "summary": str(data.get("summary", "")).strip()[:200]}
    except Exception:
        return _fallback_label(text)


# ---------------------------------------------------------------------- locate
_LOCATE_PROMPT = """You are the localisation module of a demo agent. The attached screenshot comes from a web app.
Known screens of that app:
{catalog}

Which known screen is the screenshot? If none fits, use null.
Reply with ONLY JSON: {{"screen_id": "<id or null>", "confidence": <0..1>, "reason": "<short visible cue>"}}"""


def locate(screenshot_path: str, map: dict) -> dict:  # noqa: A002 (name fixed by the contract)
    """Recognise which screen of `map` a screenshot shows.

    Stage 1: compare perceptual hashes against every screen (fast, offline).
    Stage 2: if the best match is weak or the top two are close, ask the vision
    model to choose among the candidates. Falls back to stage 1 on any LLM error.
    """
    screens = map.get("screens", []) or []
    query = screen_phash(screenshot_path)

    scored = []
    for s in screens:
        h = s.get("phash") or screen_phash(s.get("screenshot"))
        scored.append({"screen_id": s["id"], "score": _score(_hamming(query, h))})
    scored.sort(key=lambda c: c["score"], reverse=True)
    top3 = scored[:3]

    result = {
        "screen_id": top3[0]["screen_id"] if top3 else None,
        "confidence": top3[0]["score"] if top3 else 0.0,
        "candidates": top3,
        "method": "phash",
    }
    if not screens:
        return result

    best = top3[0]["score"]
    second = top3[1]["score"] if len(top3) > 1 else 0.0
    confident = best >= THRESHOLDS["locate_confident"] and best - second >= THRESHOLDS["locate_margin"]
    if confident:
        return result

    # Stage 2: ask the model. Show the phash front-runners first, then the rest.
    order = [c["screen_id"] for c in scored][: THRESHOLDS["llm_max_candidates"]]
    by_id = {s["id"]: s for s in screens}
    catalog = "\n".join(
        f'- {sid}: {by_id[sid].get("label", "")} — {by_id[sid].get("summary", "")} ({by_id[sid].get("url", "")})'
        for sid in order
    )
    try:
        reply = _ask(_LOCATE_PROMPT.format(catalog=catalog), image_path=screenshot_path, model=LOCATE_MODEL)
        data = _parse_json(reply)
        sid = data.get("screen_id")
        if sid not in by_id:
            return result if sid is not None else {**result, "screen_id": None, "confidence": 0.0, "method": "llm"}
        conf = float(data.get("confidence", 0.5))
        conf = round(min(1.0, max(0.0, conf)), 3)
        cands = [{"screen_id": sid, "score": conf}] + [c for c in top3 if c["screen_id"] != sid]
        return {
            "screen_id": sid,
            "confidence": conf,
            "candidates": cands[:3],
            "method": "llm",
            "reason": str(data.get("reason", ""))[:200],
        }
    except Exception:
        return result
