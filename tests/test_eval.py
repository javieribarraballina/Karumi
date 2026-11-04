"""
Tests for eval ground truth, measured results, Dockerfile, and pitch (Andrés: Eval, Deploy, Pitch)
"""

import json
from pathlib import Path
import re


def test_ground_truth_files():
    """Verify ground truth files exist, Basket is excluded, and regexes tolerate no trailing slash."""
    gt_dir = Path(__file__).resolve().parent.parent / "eval" / "ground_truth"
    books_file = gt_dir / "books_toscrape.json"
    assert books_file.exists(), "books_toscrape.json must exist"

    with open(books_file, "r", encoding="utf-8") as f:
        books_gt = json.load(f)

    # Basket should be removed per reviewer feedback
    assert not any("basket" in s.lower() for s in books_gt["screens"])

    # Regex patterns must match without trailing slash
    patterns = list(books_gt["url_to_screen"].keys())
    home_pattern = [p for p in patterns if "index.html" in p or books_gt["url_to_screen"][p] == "Home"][0]
    assert re.search(home_pattern, "https://books.toscrape.com")
    assert re.search(home_pattern, "https://books.toscrape.com/")


def test_demo_maps_exist():
    """Verify that benchmark demo maps exist in data/demo/."""
    base_dir = Path(__file__).resolve().parent.parent
    demo_dir = base_dir / "data" / "demo"
    assert (demo_dir / "books.json").exists() or (demo_dir / "internet.json").exists()


def test_results_markdown_has_measured_table():
    """Verify results.md exists and contains the benchmark measured table."""
    res_file = Path(__file__).resolve().parent.parent / "eval" / "results.md"
    assert res_file.exists()
    content = res_file.read_text(encoding="utf-8")
    assert "| site |" in content
    assert "locate top-1" in content


def test_dockerfile_layered_copy():
    """Verify Dockerfile uses clean layered COPY (no COPY . /app) and exposes port 8000."""
    dockerfile = Path(__file__).resolve().parent.parent / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM mcr.microsoft.com/playwright" in content
    assert "EXPOSE 8000" in content
    assert "COPY requirements.txt" in content
    assert "COPY backend/" in content
    assert "COPY frontend/" in content
    assert "COPY data/" in content
    assert "COPY eval/" in content
    assert "COPY . /app" not in content
    assert "uvicorn backend.atlas.api:app" in content


def test_pitch_members_and_calibration():
    """Verify pitch.md contains all 5 members, covers 4 criteria, and is calibrated to ~380 words (< 450 words)."""
    pitch_file = Path(__file__).resolve().parent.parent / "pitch.md"
    assert pitch_file.exists()
    content = pitch_file.read_text(encoding="utf-8")
    for member in ["Javier", "Juan", "Blanca", "Nacho", "Andrés"]:
        assert member in content, f"Member {member} missing from pitch.md"
    assert "what we built" in content.lower()
    assert "what it proves" in content.lower()
    assert "weakest part" in content.lower()
    assert "one more week" in content.lower()
    words = len(content.split())
    assert words < 450, f"pitch.md is too long ({words} words)"
