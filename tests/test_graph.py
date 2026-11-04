import json
from pathlib import Path

import pytest
from backend.atlas import graph, identify, llm

SAMPLE = json.loads((Path(__file__).parent.parent / "data/sample_map.json").read_text())


def test_sample_map_valid():
    ids = {s["id"] for s in SAMPLE["screens"]}
    assert len(ids) == 6 and len(SAMPLE["edges"]) == 7
    assert all(e["from"] in ids and e["to"] in ids for e in SAMPLE["edges"])


def raw():
    pages = [{"id": f"p{i}", "url": f"u{i}", "screenshot": f"s{i}.png", "text": f"t{i}"} for i in range(1, 5)]
    tr = [
        {"from": "p1", "to": "p2", "action": "click 'A'"},
        {"from": "p1", "to": "p3", "action": "click 'B'"},
        {"from": "p1", "to": "p4", "action": "click 'B2'"},  # same screen pair as p3, other link text -> dup edge
        {"from": "p2", "to": "p3", "action": "click 'C'"},
        {"from": "p3", "to": "p4", "action": "click 'D'"},  # self-loop after merge
    ]
    return {"app": "x", "pages": pages, "transitions": tr}


def test_build_map_dedupes_and_drops_self_loops(monkeypatch):
    monkeypatch.setattr(identify, "cluster_pages", lambda pages: [["p1"], ["p2"], ["p3", "p4"]])
    monkeypatch.setattr(identify, "label_screen", lambda shot, text: {"label": f"L-{text}", "summary": "s"})
    monkeypatch.setattr(identify, "screen_phash", lambda shot: f"h-{shot}", raising=False)
    m = graph.build_map(raw())
    assert m["screens"][2]["phash"] == "h-s3.png"  # explorer pages carry no phash
    assert [s["id"] for s in m["screens"]] == ["s1", "s2", "s3"]
    assert m["screens"][2]["page_ids"] == ["p3", "p4"]
    assert m["screens"][2]["label"] == "L-t3"  # labelled from first page of cluster
    assert {(e["from"], e["to"], e["action"]) for e in m["edges"]} == {
        ("s1", "s2", "click 'A'"), ("s1", "s3", "click 'B'"), ("s2", "s3", "click 'C'")}
    assert len(m["edges"]) == 3


def test_find_path_shortest():
    r = graph.find_path(SAMPLE, "s1", "s5")
    assert r["found"] and r["target_id"] == "s5"
    assert [s["to"] for s in r["steps"]] == ["s2", "s3", "s4", "s5"]


def test_find_path_unreachable():
    m = {"screens": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "edges": []}
    assert graph.find_path(m, "a", "b")["found"] is False


def test_find_path_same_node():
    assert graph.find_path(SAMPLE, "s1", "s1") == {"found": True, "steps": [], "target_id": "s1"}


def test_find_path_fuzzy_text_target():
    assert graph.find_path(SAMPLE, "s1", "checkout")["target_id"] == "s5"


def test_find_path_falls_back_to_llm(monkeypatch):
    monkeypatch.setattr(llm, "ask", lambda *a, **k: "s4")
    assert graph.find_path(SAMPLE, "s1", "where I pay for stuff")["target_id"] == "s4"


def test_find_path_unknown_target(monkeypatch):
    monkeypatch.setattr(llm, "ask", lambda *a, **k: "none")
    r = graph.find_path(SAMPLE, "s1", "zzzz")
    assert r["found"] is False and r["target_id"] is None


def test_find_path_unknown_start():
    assert graph.find_path(SAMPLE, "nope", "s1")["found"] is False
