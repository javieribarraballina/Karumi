"""Explorer (Juan): crawl an app it has never seen and capture its screens.

explore(url, out_dir) does a bounded, same-origin BFS with Playwright (several tabs in
parallel) and returns
the "Raw crawl" dict from README.md, also written to <out_dir>/raw.json.

Run by hand:
    python -m backend.atlas.explorer https://books.toscrape.com --out data/runs/books
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from collections import deque
from typing import Callable
from urllib.parse import unquote, urldefrag, urljoin, urlparse, urlunparse

from playwright.async_api import async_playwright

VIEWPORT = {"width": 1280, "height": 800}
PER_PATTERN = 2        # visit at most this many pages per URL pattern (/book/{n})
MAX_CHILDREN = 3       # links per page that go to the front queue: keeps the crawl going deeper
WORKERS = 4            # pages loaded in parallel (tabs of one browser)
TEXT_CHARS = 2000
MAX_LINKS = 80         # links kept per page
NAV_TIMEOUT_MS = 15000
SETTLE_MS = 2500       # extra wait for JS-rendered content, capped

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "ftp:")
SKIP_EXT = (".pdf", ".zip", ".gz", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
            ".mp4", ".mp3", ".dmg", ".exe", ".csv", ".xlsx", ".docx", ".pptx", ".xml", ".json")
DANGEROUS = re.compile(r"log[\s_-]?out|sign[\s_-]?out|delete|remove|destroy|unsubscribe|cancel[\s_-]?account", re.I)

LINKS_JS = """
() => Array.from(document.querySelectorAll('a[href]'))
  .filter(a => { const r = a.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
  .map(a => ({
    text: (a.innerText || a.getAttribute('aria-label') || a.title
           || a.querySelector('img[alt]')?.alt || a.querySelector('[aria-label]')?.getAttribute('aria-label')
           || a.querySelector('svg title')?.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
    href: a.href,
  }))
"""


# Click "Accept" on cookie/consent banners, only for buttons inside a cookie/consent box.
CONSENT_JS = r"""
() => {
  const ok = /^(accept|accept all|accept all cookies|accept cookies|allow all|allow all cookies|allow cookies|agree|i agree|got it|ok|okay|accept and close|aceptar|aceptar todo|aceptar todas|acepto|aceptar cookies|consent|continue)$/i;
  const ctx = /cookie|consent|gdpr|privacy|privacidad/i;
  const els = document.querySelectorAll('button, [role=button], input[type=button], input[type=submit], a:not([href]), a[href="#"]');
  for (const el of els) {
    const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/[.!]$/, '');
    const r = el.getBoundingClientRect();
    if (!(r.width > 0 && r.height > 0) || !ok.test(t)) continue;
    let box = el;
    for (let i = 0; i < 8 && box; i++, box = box.parentElement) {
      const bt = (box.innerText || '').slice(0, 2000);
      if (ctx.test(bt) || ctx.test(box.id || '') || ctx.test(String(box.className || ''))) { el.click(); return t; }
    }
  }
  return null;
}
"""

# Remove cookie/consent overlays that are still on screen, so they don't end up in shots or text.
STRIP_JS = r"""
() => {
  const ctx = /cookie|consent|gdpr/i;
  let n = 0;
  for (const el of Array.from(document.querySelectorAll('body *'))) {
    const cs = getComputedStyle(el);
    const floating = cs.position === 'fixed' || cs.position === 'sticky' || el.getAttribute('role') === 'dialog'
                     || el.getAttribute('aria-modal') === 'true';
    if (!floating) continue;
    const t = (el.innerText || '').slice(0, 3000);
    if (ctx.test(t) || ctx.test(el.id || '') || ctx.test(String(el.className || ''))) { el.remove(); n++; }
  }
  return n;
}
"""

HEADING_JS = r"""
() => {
  const vis = (e) => e && e.innerText && e.innerText.trim() && e.getBoundingClientRect().height > 0;
  const h = [...document.querySelectorAll('h1')].find(vis) || [...document.querySelectorAll('h2, h3')].find(vis);
  return h ? h.innerText.trim().replace(/\s+/g, ' ').slice(0, 80) : '';
}
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
            extension = re.search(r"\.[a-zA-Z]+$", seg)
            segments.append("{n}" + (extension.group() if extension else ""))
        elif len(seg) > 30 or seg.count("-") >= 4:
            segments.append("{slug}")
        else:
            segments.append(seg)
    query_keys = sorted(k.split("=")[0] for k in p.query.split("&") if k)
    return "/".join(segments) + ("?" + "&".join(query_keys) if query_keys else "")


def link_name(text: str, href: str) -> str:
    """What a person would call this link: its text, else a name made from the URL, never the URL."""
    if text and not text.lower().startswith(("http://", "https://", "//")):
        return text
    path = [seg for seg in urlparse(href).path.split("/") if seg and seg not in ("index.html", "index.htm")]
    if not path or (len(path) == 1 and len(path[0]) <= 3):   # "/" or a locale like "/es"
        return "Home"
    words = re.sub(r"\.\w+$", "", path[-1])
    words = re.sub(r"[-_+]+", " ", words).strip()
    return words[:1].upper() + words[1:] if words else "Home"


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
    return not (DANGEROUS.search(text) or DANGEROUS.search(unquote(p.path + "?" + p.query)))


def explore(url: str, out_dir: str, max_pages: int = 15, max_seconds: int = 90,
            on_progress: Callable[[int, int, str], None] | None = None, workers: int = WORKERS) -> dict:
    """Returns the Raw crawl dict; also writes <out_dir>/raw.json and shots/*.png.

    Loads `workers` pages at once (tabs of one browser). Must not be called from a running
    asyncio loop; the API calls it from a worker thread.
    """
    return asyncio.run(_explore(url, out_dir, max_pages, max_seconds, on_progress, max(1, workers)))


async def _explore(url: str, out_dir: str, max_pages: int, max_seconds: int,
                   on_progress: Callable[[int, int, str], None] | None, workers: int) -> dict:
    if "://" not in url:
        url = "https://" + url
    start = normalize_url(url)
    origin = _site(urlparse(start).netloc)
    scheme, host = urlparse(start).scheme, urlparse(start).netloc

    def canon(u: str) -> str:
        # Sites link to themselves over http/https and with/without www; treat as one page.
        u = normalize_url(u)
        p = urlparse(u)
        return urlunparse(p._replace(scheme=scheme, netloc=host)) if _site(p.netloc) == origin else u
    shots_dir = os.path.join(out_dir, "shots")
    os.makedirs(shots_dir, exist_ok=True)

    pages: list[dict] = []
    url_to_id: dict[str, str] = {}             # requested or final url -> page id
    pattern_rep: dict[str, str] = {}           # pattern -> first captured page id with it
    pattern_count = {url_pattern(start): 1}
    links_seen: list[tuple[str, str, str]] = []  # (from page id, target url, action)
    back_to: list[tuple[str, str]] = []          # (page id, page we came from)
    queue = deque([start])
    later: deque[str] = deque()                # site-menu and overflow links, visited when queue runs dry
    queued = {start}
    nav_hrefs: set[str] = set()
    came_from: dict[str, str] = {}             # queued url -> id of the page whose link we followed
    deadline = time.monotonic() + max_seconds
    next_id = 0
    active = 0                                 # pages being loaded right now (count toward max_pages)

    def report(msg: str) -> None:
        print(f"[explorer] {len(pages)}/{max_pages} {msg}", flush=True)
        if on_progress:
            try:
                on_progress(len(pages), max_pages, msg)
            except Exception:
                pass

    def left_ms() -> int:
        return max(1000, int((deadline - time.monotonic()) * 1000))

    async def visit(page, target: str) -> None:
        nonlocal next_id
        response = await page.goto(target, wait_until="domcontentloaded", timeout=min(NAV_TIMEOUT_MS, left_ms()))
        if response and "html" not in response.headers.get("content-type", "html"):
            return
        try:
            await page.wait_for_load_state("networkidle", timeout=min(SETTLE_MS, left_ms()))
        except Exception:
            pass  # analytics-heavy sites never go idle; what we have is enough
        final = canon(page.url)
        if _site(urlparse(final).netloc) != origin:
            return  # redirected off-site
        if final in url_to_id:
            url_to_id[target] = url_to_id[final]
            return  # redirect to a page we already have (or another tab is capturing it)

        # Reserve the id and URL before the next await, so two tabs never capture one page.
        next_id += 1
        pid = f"p{next_id}"
        url_to_id[target] = url_to_id[final] = pid
        try:
            try:
                if await page.evaluate(CONSENT_JS):
                    await page.wait_for_timeout(600)
                await page.evaluate(STRIP_JS)
            except Exception:
                pass  # a banner we can't handle must not lose the page
            shot = os.path.join(shots_dir, f"{pid}.png")
            await page.screenshot(path=shot, timeout=min(10000, left_ms()))
            title = await page.title()
            try:
                text = await page.inner_text("body", timeout=min(5000, left_ms()))
            except Exception:
                text = ""
            try:
                heading = await page.evaluate(HEADING_JS)
            except Exception:
                heading = ""
            raw_links = await page.evaluate(LINKS_JS)
            here = page.url
        except Exception:
            for k in [k for k, v in url_to_id.items() if v == pid]:
                del url_to_id[k]
            raise

        # From here on no awaits: the shared queues change atomically.
        # Lead with the page's own heading (h1, else first h2/h3) so labels differ per
        # screen; never the site-wide <title>, which is often the same on every page.
        text = (heading + "\n" + text if heading else text)[:TEXT_CHARS]
        links = []
        for link in raw_links:
            href = canon(urljoin(here, link["href"]))
            if _should_follow(href, link["text"], origin):
                links.append({"text": link["text"], "href": href})
        links = list({l["href"]: l for l in links}.values())[:MAX_LINKS]

        pages.append({"id": pid, "url": final, "title": title,
                      "screenshot": shot, "text": text, "links": links})
        if target in came_from:
            back_to.append((pid, came_from[target]))
        pattern_rep.setdefault(url_pattern(final), pid)
        report(final)

        if not nav_hrefs:
            nav_hrefs.update(l["href"] for l in links)  # the start page's links ~ site menu
        for link in links:
            links_seen.append((pid, link["href"], f"click '{link_name(link['text'], link['href'])}'"))
        # Content links (not in the site-wide menu) go first, so each page leads one level
        # deeper; menu links and overflow wait in `later` so breadth isn't lost.
        new = 0
        for link in sorted(links, key=lambda l: l["href"] in nav_hrefs and pid != "p1"):
            href = link["href"]
            if href in queued:
                continue
            pat = url_pattern(href)
            if pattern_count.get(pat, 0) >= PER_PATTERN:
                continue
            pattern_count[pat] = pattern_count.get(pat, 0) + 1
            queued.add(href)
            came_from.setdefault(href, pid)
            menu = href in nav_hrefs and pid != "p1"
            if not menu and new < MAX_CHILDREN:
                queue.append(href)
                new += 1
            else:
                later.append(href)

    async def worker(page) -> None:
        nonlocal active
        while len(pages) < max_pages and time.monotonic() < deadline:
            # Menu links only when no deeper link is waiting and at most one tab is busy:
            # busy tabs are about to add content links, which should go first.
            use_later = not queue and later and active <= 1
            if not queue and not use_later:
                if active == 0 and not later:
                    return  # nothing left anywhere
                await asyncio.sleep(0.05)
                continue
            if len(pages) + active >= max_pages:
                await asyncio.sleep(0.05)  # enough pages in flight to hit the limit
                continue
            target = queue.popleft() if queue else later.popleft()
            active += 1
            try:
                await visit(page, target)
            except Exception as exc:  # one bad page must not kill the run
                report(f"skip {target}: {type(exc).__name__}")
            finally:
                active -= 1

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(viewport=VIEWPORT, accept_downloads=False)
            tabs = [await context.new_page() for _ in range(workers)]
            await asyncio.gather(*(worker(tab) for tab in tabs))
        finally:
            await browser.close()

    # A link to a page we skipped (pattern full) still points at that kind of screen,
    # so route it to the first captured page whose final URL has the same pattern.
    transitions, seen_edges = [], set()
    for src, href, action in links_seen:
        dst = url_to_id.get(href) or pattern_rep.get(url_pattern(href))
        if dst and dst != src and (src, dst) not in seen_edges:
            seen_edges.add((src, dst))
            transitions.append({"from": src, "to": dst, "action": action})

    # The browser Back button always returns the way we came: add it where the page itself
    # has no link back (dead ends, pages that only link off-site). Real links win.
    for src, dst in back_to:
        if src != dst and (src, dst) not in seen_edges:
            seen_edges.add((src, dst))
            transitions.append({"from": src, "to": dst, "action": "go back"})

    # Tabs finish out of order; keep pages in id order (p1 = start page) for readers.
    pages.sort(key=lambda p: int(p["id"][1:]))
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
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()
    explore(args.url, args.out, args.max_pages, args.max_seconds, workers=args.workers)
