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
from urllib.parse import unquote, urldefrag, urljoin, urlparse, urlunparse

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
DANGEROUS = re.compile(r"log[\s_-]?out|sign[\s_-]?out|delete|remove|destroy|unsubscribe|cancel[\s_-]?account", re.I)

LINKS_JS = """
() => Array.from(document.querySelectorAll('a[href]'))
  .filter(a => { const r = a.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
  .map(a => ({
    text: (a.innerText || a.getAttribute('aria-label') || a.title || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
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
() => { const h = document.querySelector('h1'); return h ? h.innerText.trim().replace(/\s+/g, ' ').slice(0, 80) : ''; }
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
            on_progress: Callable[[int, int, str], None] | None = None) -> dict:
    """Returns the Raw crawl dict; also writes <out_dir>/raw.json and shots/*.png"""
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
    queue = deque([start])
    queued = {start}
    deadline = time.monotonic() + max_seconds

    def report(msg: str) -> None:
        print(f"[explorer] {len(pages)}/{max_pages} {msg}", flush=True)
        if on_progress:
            try:
                on_progress(len(pages), max_pages, msg)
            except Exception:
                pass

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport=VIEWPORT, accept_downloads=False)
            page = context.new_page()
            while queue and len(pages) < max_pages and time.monotonic() < deadline:
                target = queue.popleft()
                left_ms = lambda: max(1000, int((deadline - time.monotonic()) * 1000))  # noqa: E731
                try:
                    response = page.goto(target, wait_until="domcontentloaded",
                                         timeout=min(NAV_TIMEOUT_MS, left_ms()))
                    if response and "html" not in response.headers.get("content-type", "html"):
                        continue
                    try:
                        page.wait_for_load_state("networkidle", timeout=min(SETTLE_MS, left_ms()))
                    except Exception:
                        pass  # analytics-heavy sites never go idle; what we have is enough
                    final = canon(page.url)
                    if _site(urlparse(final).netloc) != origin:
                        continue  # redirected off-site
                    if final in url_to_id:
                        url_to_id[target] = url_to_id[final]
                        continue  # redirect to a page we already have

                    try:
                        if page.evaluate(CONSENT_JS):
                            page.wait_for_timeout(600)
                        page.evaluate(STRIP_JS)
                    except Exception:
                        pass  # a banner we can't handle must not lose the page

                    pid = f"p{len(pages) + 1}"
                    shot = os.path.join(shots_dir, f"{pid}.png")
                    page.screenshot(path=shot, timeout=min(10000, left_ms()))
                    title = page.title()
                    try:
                        text = page.inner_text("body", timeout=min(5000, left_ms()))
                    except Exception:
                        text = ""
                    try:
                        heading = page.evaluate(HEADING_JS)
                    except Exception:
                        heading = ""
                    # Lead with what names this page (h1, else <title>) so labels differ per screen.
                    name = heading or title.split(" | ")[0].split(" - ")[0].strip()
                    text = (name + "\n" + text if name else text)[:TEXT_CHARS]
                    links = []
                    for link in page.evaluate(LINKS_JS):
                        href = canon(urljoin(page.url, link["href"]))
                        if _should_follow(href, link["text"], origin):
                            links.append({"text": link["text"], "href": href})
                    links = list({l["href"]: l for l in links}.values())[:MAX_LINKS]

                    pages.append({"id": pid, "url": final, "title": title,
                                  "screenshot": shot, "text": text, "links": links})
                    url_to_id[target] = url_to_id[final] = pid
                    pattern_rep.setdefault(url_pattern(final), pid)
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
                        queued.add(href)
                        queue.append(href)
                except Exception as exc:  # one bad page must not kill the run
                    report(f"skip {target}: {type(exc).__name__}")
        finally:
            browser.close()

    # A link to a page we skipped (pattern full) still points at that kind of screen,
    # so route it to the first captured page whose final URL has the same pattern.
    transitions, seen_edges = [], set()
    for src, href, action in links_seen:
        dst = url_to_id.get(href) or pattern_rep.get(url_pattern(href))
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
