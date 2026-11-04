import functools
import http.server
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.atlas.explorer import explore, normalize_url, url_pattern  # noqa: E402

SITE = {
    "index.html": '<h1>Home</h1><a href="about.html">About</a> <a href="products.html">Products</a>'
                  ' <a href="mailto:hi@example.com">Mail</a> <a href="https://external.example.com/">Ext</a>'
                  ' <a href="#top">Top</a> <a href="logout.html">Log out</a> <a href="report.pdf">PDF</a>',
    "about.html": '<h1>About</h1><a href="index.html">Home</a>',
    "logout.html": "<h1>Bye</h1>",
    "products.html": "<h1>Products</h1>" + "".join(f'<a href="item/{i}.html">Item {i}</a> ' for i in range(1, 11)),
    **{f"item/{i}.html": f'<h1>Item {i}</h1><a href="../products.html">Back</a>' for i in range(1, 11)},
}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    for name, body in SITE.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(f"<html><body>{body}</body></html>")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


@pytest.fixture(scope="module")
def crawl(site, tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    return explore(site, str(out), max_pages=15, max_seconds=60), out


def paths(raw):
    return {p["url"].split("/", 3)[3] for p in raw["pages"]}


def test_normalize_url():
    assert normalize_url("http://A.com/x/index.html#frag") == "http://a.com/x"
    assert normalize_url("http://a.com/x/") == "http://a.com/x"
    assert normalize_url("http://a.com") == "http://a.com/"


def test_url_pattern_collapses_ids_and_slugs():
    assert url_pattern("https://a.com/book/12") == url_pattern("https://a.com/book/99")
    assert url_pattern("https://a.com/catalogue/travel_2/index.html") == url_pattern(
        "https://a.com/catalogue/mystery_3/index.html")
    assert url_pattern("https://a.com/about") != url_pattern("https://a.com/pricing")


def test_url_pattern_separates_listing_and_product_pages():
    assert url_pattern("https://books.toscrape.com/catalogue/page-2.html") != url_pattern(
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000")


@pytest.mark.parametrize("first, second", [
    ("/catalogue/a-light-in-the-attic_1000", "/catalogue/tipping-the-velvet_999"),
    ("/catalogue/page-2.html", "/catalogue/page-3.html"),
    ("/catalogue/category/books/travel_2", "/catalogue/category/books/mystery_3"),
    ("/catalogue/category/books/mystery_3", "/catalogue/category/books/historical-fiction_4"),
    ("/category/books/travel_2/page-2.html", "/category/books/mystery_3/page-2.html"),
    ("/book/12", "/book/99"),
    ("/item/1.html", "/item/2.html"),
])
def test_url_pattern_collapses_same_kind_pages(first, second):
    assert url_pattern("https://a.com" + first) == url_pattern("https://a.com" + second)


@pytest.mark.parametrize("segment, expected", [
    ("page-2.html", "{n}.html"),
    ("page-2.htm", "{n}.htm"),
    ("page-2.php", "{n}.php"),
    ("v1.2", "{n}"),
    ("v1.html2", "{n}"),
])
def test_url_pattern_preserves_only_final_letter_extensions(segment, expected):
    assert url_pattern("https://a.com/" + segment) == "/" + expected


def test_url_pattern_keeps_query_keys_distinct():
    assert url_pattern("https://a.com/?search=x") != url_pattern("https://a.com/?login=1")


def test_crawl_matches_contract(crawl):
    raw, out = crawl
    assert set(raw) == {"app", "pages", "transitions"}
    for p in raw["pages"]:
        assert set(p) == {"id", "url", "title", "screenshot", "text", "links"}
        assert os.path.getsize(p["screenshot"]) > 0
    for t in raw["transitions"]:
        assert set(t) == {"from", "to", "action"}
    assert (out / "raw.json").exists()


def test_visits_expected_pages(crawl):
    raw, _ = crawl
    found = paths(raw)
    assert {"", "about.html", "products.html"} <= found
    items = [p for p in found if p.startswith("item/")]
    assert 1 <= len(items) <= 2, "URL-pattern limiter should cap item pages at 2"


def test_skips_external_mailto_logout_and_files(crawl):
    raw, _ = crawl
    urls = " ".join(p["url"] for p in raw["pages"])
    assert "external" not in urls and "logout" not in urls and ".pdf" not in urls
    hrefs = " ".join(l["href"] for p in raw["pages"] for l in p["links"])
    assert "mailto:" not in hrefs and "logout" not in hrefs


def test_transitions_connect_pages(crawl):
    raw, _ = crawl
    by_path = {p["url"].split("/", 3)[3]: p["id"] for p in raw["pages"]}
    edges = {(t["from"], t["to"]) for t in raw["transitions"]}
    assert (by_path[""], by_path["about.html"]) in edges
    assert (by_path["about.html"], by_path[""]) in edges
    assert all(f != t for f, t in edges)
    assert len(edges) == len(raw["transitions"]), "no duplicate edges"
    # skipped item pages still route to a visited item page
    item_ids = {pid for path, pid in by_path.items() if path.startswith("item/")}
    assert any(f == by_path["products.html"] and t in item_ids for f, t in edges)


def test_max_pages_is_respected(site, tmp_path):
    raw = explore(site, str(tmp_path), max_pages=2, max_seconds=30)
    assert len(raw["pages"]) == 2


def test_bad_url_does_not_crash(tmp_path):
    raw = explore("http://127.0.0.1:9/", str(tmp_path), max_pages=3, max_seconds=10)
    assert raw["pages"] == []


@pytest.mark.parametrize("href,text", [
    ("http://a.com/?action=delete", "Go"), ("http://a.com/log-out", "Bye"), ("http://a.com/sign_out", "x"),
    ("http://a.com/account/remove", "Settings"), ("http://a.com/ok", "Log out"),
])
def test_dangerous_links_are_never_followed(href, text):
    from backend.atlas.explorer import _should_follow
    assert not _should_follow(href, text, "a.com")


def test_safe_links_are_followed():
    from backend.atlas.explorer import _should_follow
    assert _should_follow("http://www.a.com/pricing", "Pricing", "a.com")


def test_progress_callback_errors_do_not_abort(site, tmp_path):
    def boom(*a):
        raise RuntimeError("ui went away")
    raw = explore(site, str(tmp_path), max_pages=2, max_seconds=30, on_progress=boom)
    assert len(raw["pages"]) == 2 and (tmp_path / "raw.json").exists()


def test_time_budget_is_respected(site, tmp_path):
    import time
    t = time.monotonic()
    explore(site, str(tmp_path), max_pages=50, max_seconds=2)
    assert time.monotonic() - t < 8  # budget + browser start/stop
