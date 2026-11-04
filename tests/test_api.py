import json
import time

import pytest
from fastapi.testclient import TestClient
from backend.atlas import api, explorer, graph, identify

client = TestClient(api.app)


def test_sample_map():
    r = client.get("/api/maps/sample")
    assert r.status_code == 200 and len(r.json()["screens"]) == 6


def test_list_maps_includes_sample():
    assert "sample" in client.get("/api/maps").json()


def test_unknown_map_404_with_message():
    r = client.get("/api/maps/nope")
    assert r.status_code == 404 and "nope" in r.json()["detail"]


def test_path_route():
    r = client.get("/api/maps/sample/path", params={"from": "s1", "to": "s5"})
    assert r.status_code == 200 and r.json()["found"] is True


def test_path_honours_from():
    r = client.get("/api/maps/sample/path", params={"from": "s3", "to": "s5"}).json()
    assert [x["to"] for x in r["steps"]] == ["s4", "s5"]


def test_locate_delegates(monkeypatch):
    monkeypatch.setattr(identify, "locate", lambda p, m: {"screen_id": "s3", "confidence": 1.0, "candidates": []})
    r = client.post("/api/maps/sample/locate", files={"file": ("a.png", b"\x89PNG", "image/png")})
    assert r.json()["screen_id"] == "s3"


def test_locate_error_is_readable(monkeypatch):
    def boom(p, m):
        raise NotImplementedError

    monkeypatch.setattr(identify, "locate", boom)
    r = client.post("/api/maps/sample/locate", files={"file": ("a.png", b"x", "image/png")})
    assert r.status_code == 500 and r.json()["detail"]


def wait_done(job_id):
    for _ in range(50):
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job never finished")


def test_explore_job_done(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(explorer, "explore", lambda url, out_dir, **k: {"app": url, "pages": [], "transitions": []})
    monkeypatch.setattr(graph, "build_map", lambda raw: {"app": raw["app"], "screens": [], "edges": []})
    job = client.post("/api/explore", json={"url": "http://x"}).json()["job_id"]
    j = wait_done(job)
    assert j["status"] == "done"
    assert client.get(f"/api/maps/{j['map_id']}").json()["app"] == "http://x"


def test_explore_job_reports_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path)
    seen = {}

    def fake(url, out_dir, on_progress=None, **k):
        on_progress(7, 15, "http://x/a")
        seen["mid"] = list(api.JOBS.values())[-1]["progress"]
        return {"app": url, "pages": [], "transitions": []}

    monkeypatch.setattr(explorer, "explore", fake)
    monkeypatch.setattr(graph, "build_map", lambda raw: {"app": "x", "screens": [], "edges": []})
    job = client.post("/api/explore", json={"url": "http://x"}).json()["job_id"]
    wait_done(job)
    assert seen["mid"] == "7/15 pages"


def test_explore_limits_default_and_override(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path)
    seen = []
    monkeypatch.setattr(explorer, "explore", lambda url, out_dir, **k: seen.append(k) or {"app": url, "pages": [], "transitions": []})
    monkeypatch.setattr(graph, "build_map", lambda raw: {"app": "x", "screens": [], "edges": []})
    wait_done(client.post("/api/explore", json={"url": "http://x"}).json()["job_id"])
    wait_done(client.post("/api/explore", json={"url": "http://x", "max_pages": 40, "max_seconds": 300}).json()["job_id"])
    assert (seen[0]["max_pages"], seen[0]["max_seconds"]) == (60, 180)
    assert (seen[1]["max_pages"], seen[1]["max_seconds"]) == (40, 300)


def test_explore_job_error(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path)

    def boom(*a, **k):
        raise RuntimeError("site down")

    monkeypatch.setattr(explorer, "explore", boom)
    j = wait_done(client.post("/api/explore", json={"url": "http://x"}).json()["job_id"])
    assert j["status"] == "error" and "site down" in j["error"]


def test_unknown_job_404():
    assert client.get("/api/jobs/zzz").status_code == 404
