"""Tests for backend/atlas/identify.py (Blanca). Run offline: the LLM is stubbed."""
import json
import os
import random
import sys

import pytest
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from atlas import identify  # noqa: E402


# ------------------------------------------------------------------ fixtures
def make_screen(path, seed, size=(400, 300)):
    """A fake app screen: header bar, sidebar and random blocks. Different seeds look different."""
    rnd = random.Random(seed)
    im = Image.new("RGB", size, (245, 245, 245))
    d = ImageDraw.Draw(im)
    w, h = size
    d.rectangle([0, 0, w, h * 0.12], fill=tuple(rnd.randint(0, 255) for _ in range(3)))
    if rnd.random() > 0.5:
        d.rectangle([0, h * 0.12, w * 0.22, h], fill=tuple(rnd.randint(0, 200) for _ in range(3)))
    for _ in range(6):
        x0, y0 = rnd.uniform(0.25, 0.8) * w, rnd.uniform(0.15, 0.8) * h
        x1, y1 = x0 + rnd.uniform(0.1, 0.3) * w, y0 + rnd.uniform(0.05, 0.25) * h
        d.rectangle([x0, y0, x1, y1], fill=tuple(rnd.randint(0, 255) for _ in range(3)))
    im.save(path)
    return str(path)


def as_user_screenshot(src, dst, scale=0.8):
    """Simulate a user's screenshot: resized and re-saved as JPEG."""
    with Image.open(src) as im:
        im = im.resize((int(im.width * scale), int(im.height * scale)))
        im.convert("RGB").save(dst, "JPEG", quality=80)
    return str(dst)


@pytest.fixture
def no_llm(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("LLM offline in tests")

    monkeypatch.setattr(identify, "_ask", boom)


@pytest.fixture
def sample_map(tmp_path):
    labels = ["Home", "Category listing", "Product detail", "Basket", "Login", "Account settings"]
    screens = []
    for i, label in enumerate(labels, start=1):
        shot = make_screen(tmp_path / f"s{i}.png", seed=i * 7)
        screens.append(
            {
                "id": f"s{i}",
                "label": label,
                "summary": f"{label} screen.",
                "url": f"https://shop.test/{label.lower().replace(' ', '-')}",
                "screenshot": shot,
                "phash": identify.screen_phash(shot),
            }
        )
    return {"app": "https://shop.test", "screens": screens, "edges": []}


# ---------------------------------------------------------------- url_pattern
@pytest.mark.parametrize(
    "a,b",
    [
        ("https://x.com/book/123", "https://x.com/book/9"),
        (
            "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
            "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
        ),
        ("https://x.com/a?page=1", "https://x.com/a?page=2#top"),
    ],
)
def test_url_pattern_same_template(a, b):
    assert identify.url_pattern(a) == identify.url_pattern(b)


def test_url_pattern_keeps_different_screens_apart():
    p = identify.url_pattern
    assert p("https://x.com/") != p("https://x.com/login")
    # a paginated listing must not collide with a product detail page
    assert p("https://books.toscrape.com/catalogue/page-2.html") != p(
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )


# -------------------------------------------------------------- cluster_pages
def test_cluster_merges_same_url_pattern_with_different_content(tmp_path):
    pages = [
        {"id": "p1", "url": "https://x.com/book/1", "screenshot": make_screen(tmp_path / "a.png", 1)},
        {"id": "p2", "url": "https://x.com/book/2", "screenshot": make_screen(tmp_path / "b.png", 2)},
    ]
    assert identify.cluster_pages(pages) == [["p1", "p2"]]


def test_cluster_keeps_visually_different_pages_apart(tmp_path):
    pages = [
        {"id": "p1", "url": "https://x.com/", "screenshot": make_screen(tmp_path / "a.png", 11)},
        {"id": "p2", "url": "https://x.com/login", "screenshot": make_screen(tmp_path / "b.png", 22)},
    ]
    assert identify.cluster_pages(pages) == [["p1"], ["p2"]]


def test_cluster_merges_identical_screens_with_different_urls(tmp_path):
    shot = make_screen(tmp_path / "a.png", 5)
    pages = [
        {"id": "p1", "url": "https://x.com/", "screenshot": shot},
        {"id": "p2", "url": "https://x.com/home", "screenshot": as_user_screenshot(shot, tmp_path / "b.jpg", 1.0)},
        {"id": "p3", "url": "https://x.com/login", "screenshot": make_screen(tmp_path / "c.png", 99)},
    ]
    assert identify.cluster_pages(pages) == [["p1", "p2"], ["p3"]]


def white_page(path, n):
    """Near-identical white pages (same header, a heading of slightly different width),
    like the plain pages of the-internet.herokuapp.com."""
    im = Image.new("RGB", (400, 300), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 400, 24], fill=(40, 40, 40))
    d.rectangle([20, 50, 180 + 6 * n, 62], fill=(60, 60, 60))
    im.save(path)
    return str(path)


def test_cluster_does_not_merge_white_pages_with_different_text(tmp_path):
    texts = [
        "Checkboxes checkbox 1 checkbox 2",
        "Dropdown List Please select an option",
        "Login Page This is where you can log into the secure area",
        "Key Presses Key presses are often used to interact with a website",
        "Hovers Hover over the image for additional information",
    ]
    pages = [
        {"id": f"p{i}", "url": f"https://the-internet.test/{t.split()[0].lower()}", "text": t,
         "screenshot": white_page(tmp_path / f"w{i}.png", i)}
        for i, t in enumerate(texts, start=1)
    ]
    # the screenshots really are visually close, so only the text check keeps them apart
    hs = [identify.screen_phash(p["screenshot"]) for p in pages]
    assert max(identify._hamming(hs[0], h) for h in hs) <= identify.THRESHOLDS["phash_same_screen"]
    assert identify.cluster_pages(pages) == [[p["id"]] for p in pages]


def test_cluster_merges_similar_pages_when_text_overlaps(tmp_path):
    shot = make_screen(tmp_path / "a.png", 5)
    pages = [
        {"id": "p1", "url": "https://x.com/", "text": "Welcome to Acme dashboard revenue tasks today",
         "screenshot": shot},
        {"id": "p2", "url": "https://x.com/home", "text": "Welcome to Acme dashboard revenue tasks this week",
         "screenshot": as_user_screenshot(shot, tmp_path / "b.jpg", 1.0)},
    ]
    assert identify.cluster_pages(pages) == [["p1", "p2"]]


def test_word_overlap():
    assert identify._overlap(identify._words("Log in now"), identify._words("log IN now!")) == 1.0
    assert identify._overlap(identify._words("a b"), identify._words("c d")) == 0.0
    assert identify._overlap(set(), {"a"}) == 0.0


def test_cluster_is_transitive_and_survives_missing_screenshots():
    pages = [
        {"id": "p1", "url": "https://x.com/item/1"},
        {"id": "p2", "url": "https://x.com/about", "screenshot": "does/not/exist.png"},
        {"id": "p3", "url": "https://x.com/item/2"},
        {"id": "p4", "url": "https://x.com/item/3"},
    ]
    assert identify.cluster_pages(pages) == [["p1", "p3", "p4"], ["p2"]]


# ---------------------------------------------------------------- label_screen
def test_label_screen_parses_model_json(monkeypatch, tmp_path):
    reply = '```json\n{"label": "Product detail", "summary": "See a book and add it to the basket."}\n```'
    monkeypatch.setattr(identify, "_ask", lambda *a, **k: reply)
    out = identify.label_screen(make_screen(tmp_path / "a.png", 1), "A Light in the Attic\n£51.77")
    assert out == {"label": "Product detail", "summary": "See a book and add it to the basket."}


def test_label_screen_garbage_falls_back_without_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(identify, "_ask", lambda *a, **k: "sorry, I can't")
    out = identify.label_screen(make_screen(tmp_path / "a.png", 1), "\n  Books to Scrape  \nAll products")
    assert out == {"label": "Books to Scrape", "summary": ""}


def test_label_screen_llm_error_falls_back(no_llm, tmp_path):
    out = identify.label_screen(make_screen(tmp_path / "a.png", 1), "")
    assert out["label"] == "Unnamed screen"


# --------------------------------------------------------------------- locate
def test_locate_resized_jpeg_resolves_to_same_screen(no_llm, sample_map, tmp_path):
    hits = 0
    for s in sample_map["screens"]:
        upload = as_user_screenshot(s["screenshot"], tmp_path / f"user_{s['id']}.jpg", 0.8)
        out = identify.locate(upload, sample_map)
        assert set(out) >= {"screen_id", "confidence", "candidates"}
        assert len(out["candidates"]) == 3
        assert 0.0 <= out["confidence"] <= 1.0
        hits += out["screen_id"] == s["id"]
    acc = hits / len(sample_map["screens"])
    print(f"\nlocate top-1 accuracy (phash only, 80% JPEG): {acc:.0%} ({hits}/{len(sample_map['screens'])})")
    assert acc == 1.0


def test_locate_asks_llm_when_ambiguous(monkeypatch, sample_map, tmp_path):
    # two screens with the same picture: phash cannot tell them apart
    sample_map["screens"][1]["screenshot"] = sample_map["screens"][0]["screenshot"]
    sample_map["screens"][1]["phash"] = sample_map["screens"][0]["phash"]
    calls = []

    def fake(prompt, image_path=None, model="haiku"):
        calls.append(prompt)
        return json.dumps({"screen_id": "s2", "confidence": 0.9, "reason": "category sidebar"})

    monkeypatch.setattr(identify, "_ask", fake)
    out = identify.locate(sample_map["screens"][0]["screenshot"], sample_map)
    assert calls and "s1" in calls[0] and "s2" in calls[0]
    assert out["screen_id"] == "s2" and out["method"] == "llm" and out["confidence"] == 0.9


def test_locate_ignores_invented_screen_id(monkeypatch, sample_map):
    sample_map["screens"][1]["phash"] = sample_map["screens"][0]["phash"]
    monkeypatch.setattr(identify, "_ask", lambda *a, **k: '{"screen_id": "s99", "confidence": 1}')
    out = identify.locate(sample_map["screens"][0]["screenshot"], sample_map)
    assert out["screen_id"] in {"s1", "s2"} and out["method"] == "phash"


def test_locate_empty_map(no_llm, tmp_path):
    out = identify.locate(make_screen(tmp_path / "a.png", 1), {"screens": []})
    assert out["screen_id"] is None and out["candidates"] == []
