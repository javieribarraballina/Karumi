"""Explorer (Juan): crawl an app it has never seen and capture its screens.

explore(url, out_dir) does a bounded, same-origin BFS with Playwright and returns
the "Raw crawl" dict from README.md, also written to <out_dir>/raw.json.

Run by hand:
    python -m backend.atlas.explorer https://books.toscrape.com --out data/runs/books
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import deque
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1280, "height": 800}
PER_PATTERN = 2        # visit at most this many pages per URL pattern (/book/{n})
TEXT_CHARS = 2000
MAX_LINKS = 80         # links kept per page
NAV_TIMEOUT_MS = 15000
SETTLE_MS = 2500       # extra wait for JS-rendered content, capped

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "ftp:")
SKIP_EXT = (".pdf", ".zip", ".gz", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
            ".mp4", ".mp3", ".dmg", ".exe", ".csv", ".xlsx", ".docx", ".pptx", ".xml", ".json")
DANGEROUS = re.compile(r"log\s?out|sign\s?out|delete|remove|unsubscribe|cancel account", re.I)

LINKS_JS = """
() => Array.from(document.querySelectorAll('a[href]'))
  .filter(a => { const r = a.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
  .map(a => ({
    text: (a.innerText || a.getAttribute('aria-label') || a.title || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
    href: a.href,
  }))
"""


def normalize_url(url: str) -> str:
    """Canonical form used to tell whether two links point at the same page."""
    url, _ = urldefrag(url.strip())
    p = urlparse(url)
    path = re.sub(r"/index\.html?$", "/", p.path) or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))


def url_pattern(url: str) -> str:
    """Collapse ids and slugs so /book/12 and /book/99 share one pattern."""
    p = urlparse(normalize_url(url))
    segments = []
    for seg in p.path.split("/"):
        if re.search(r"\d", seg):
            segments.append("{n}")
        elif len(seg) > 30 or seg.count("-") >= 4:
            segments.append("{slug}")
        else:
            segments.append(seg)
    query_keys = sorted(k.split("=")[0] for k in p.query.split("&") if k)
    return "/".join(segments) + ("?" + "&".join(query_keys) if query_keys else "")


def _site(netloc: str) -> str:
    return netloc.lower().removeprefix("www.")


def _should_follow(href: str, text: str, origin: str) -> bool:
    if not href or href.lower().startswith(SKIP_SCHEMES):
        return False
    p = urlparse(href)
    if p.scheme not in ("http", "https") or _site(p.netloc) != origin:
        return False
    if p.path.lower().endswith(SKIP_EXT):
        return False
    return not (DANGEROUS.search(text) or DANGEROUS.search(p.path))


def explore(url: str, out_dir: str, max_pages: int = 15, max_seconds: int = 90,
            on_progress: Callable[[int, int, str], None] | None = None) -> dict:
    """Returns the Raw crawl dict; also writes <out_dir>/raw.json and shots/*.png"""
    if "://" not in url:
        url = "https://" + url
    start = normalize_url(url)
    origin = _site(urlparse(start).netloc)
    scheme = urlparse(start).scheme

    def canon(u: str) -> str:
        # Sites often link to themselves over http and https; treat both as one page.
        u = normalize_url(u)
        p = urlparse(u)
        return urlunparse(p._replace(scheme=scheme)) if _site(p.netloc) == origin else u
    shots_dir = os.path.join(out_dir, "shots")
    os.makedirs(shots_dir, exist_ok=True)

    pages: list[dict] = []
    url_to_id: dict[str, str] = {}             # requested or final url -> page id
    pattern_first = {url_pattern(start): start}  # pattern -> first url queued with it
    pattern_count = {url_pattern(start): 1}
    links_seen: list[tuple[str, str, str]] = []  # (from page id, target url, action)
    queue = deque([start])
    queued = {start}
    deadline = time.monotonic() + max_seconds

    def report(msg: str) -> None:
        print(f"[explorer] {len(pages)}/{max_pages} {msg}", flush=True)
        if on_progress:
            on_progress(len(pages), max_pages, msg)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport=VIEWPORT, accept_downloads=False)
            page = context.new_page()
            while queue and len(pages) < max_pages and time.monotonic() < deadline:
                target = queue.popleft()
                try:
                    response = page.goto(target, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                    if response and "html" not in response.headers.get("content-type", "html"):
                        continue
                    try:
                        page.wait_for_load_state("networkidle", timeout=SETTLE_MS)
                    except Exception:
                        pass  # analytics-heavy sites never go idle; what we have is enough
                    final = canon(page.url)
                    if _site(urlparse(final).netloc) != origin:
                        continue  # redirected off-site
                    if final in url_to_id:
                        url_to_id[target] = url_to_id[final]
                        continue  # redirect to a page we already have

                    pid = f"p{len(pages) + 1}"
                    shot = os.path.join(shots_dir, f"{pid}.png")
                    page.screenshot(path=shot)
                    try:
                        text = page.inner_text("body")[:TEXT_CHARS]
                    except Exception:
                        text = ""
                    links = []
                    for link in page.evaluate(LINKS_JS):
                        href = canon(urljoin(page.url, link["href"]))
                        if _should_follow(href, link["text"], origin):
                            links.append({"text": link["text"], "href": href})
                    links = list({l["href"]: l for l in links}.values())[:MAX_LINKS]

                    pages.append({"id": pid, "url": final, "title": page.title(),
                                  "screenshot": shot, "text": text, "links": links})
                    url_to_id[target] = url_to_id[final] = pid
                    report(final)

                    for link in links:
                        href = link["href"]
                        links_seen.append((pid, href, f"click '{link['text'] or href}'"))
                        if href in queued:
                            continue
                        pat = url_pattern(href)
                        if pattern_count.get(pat, 0) >= PER_PATTERN:
                            continue
                        pattern_count[pat] = pattern_count.get(pat, 0) + 1
                        pattern_first.setdefault(pat, href)
                        queued.add(href)
                        queue.append(href)
                except Exception as exc:  # one bad page must not kill the run
                    report(f"skip {target}: {type(exc).__name__}")
        finally:
            browser.close()

    # A link to a page we skipped (pattern full) still points at that kind of screen,
    # so route it to the first visited page with the same pattern.
    transitions, seen_edges = [], set()
    for src, href, action in links_seen:
        dst = url_to_id.get(href) or url_to_id.get(pattern_first.get(url_pattern(href), ""))
        if dst and dst != src and (src, dst) not in seen_edges:
            seen_edges.add((src, dst))
            transitions.append({"from": src, "to": dst, "action": action})

    raw = {"app": start, "pages": pages, "transitions": transitions}
    with open(os.path.join(out_dir, "raw.json"), "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    report(f"done: {len(pages)} pages, {len(transitions)} transitions")
    return raw


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Crawl an app and write raw.json + screenshots")
    ap.add_argument("url")
    ap.add_argument("--out", default="data/runs/latest")
    ap.add_argument("--max-pages", type=int, default=15)
    ap.add_argument("--max-seconds", type=int, default=90)
    args = ap.parse_args()
    explore(args.url, args.out, args.max_pages, args.max_seconds)
