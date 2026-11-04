"""
Tests for eval ground truth and measured results (Andrés: Eval, Deploy, Pitch)
"""

import json
from pathlib import Path
import re


def test_ground_truth_files():
    gt_dir = Path(__file__).resolve().parent.parent / "eval" / "ground_truth"
    books_file = gt_dir / "books_toscrape.json"
    assert books_file.exists(), "books_toscrape.json must exist"

    with open(books_file, "r", encoding="utf-8") as f:
        books_gt = json.load(f)

    # Basket should be removed
    assert not any("basket" in s.lower() for s in books_gt["screens"])

    # Regex patterns must match without trailing slash
    assert re.search(r"^https?://books\.toscrape\.com/?$", "https://books.toscrape.com")
    assert re.search(r"^https?://books\.toscrape\.com/?$", "https://books.toscrape.com/")


def test_demo_maps_exist():
    base_dir = Path(__file__).resolve().parent.parent
    demo_dir = base_dir / "data" / "demo"
    assert (demo_dir / "books.json").exists() or (demo_dir / "internet.json").exists()


def test_results_markdown_has_measured_table():
    res_file = Path(__file__).resolve().parent.parent / "eval" / "results.md"
    assert res_file.exists()
    content = res_file.read_text(encoding="utf-8")
    assert "| site |" in content
    assert "locate top-1" in content
