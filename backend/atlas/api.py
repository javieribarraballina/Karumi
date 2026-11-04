import json
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import explorer, graph, identify

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RUNS_DIR = DATA / "runs"
JOBS: dict[str, dict] = {}  # shortcut: in memory, lost on restart; persist only if the demo needs it

app = FastAPI()


def _map_file(map_id: str) -> Path | None:
    first = DATA / "sample_map.json" if map_id == "sample" else DATA / "demo" / f"{map_id}.json"
    return next((f for f in (first, RUNS_DIR / map_id / "map.json") if f.is_file()), None)


def _load(map_id: str) -> dict:
    f = _map_file(map_id) if "/" not in map_id and ".." not in map_id else None
    if not f:
        raise HTTPException(404, f"Map '{map_id}' not found")
    return json.loads(f.read_text())


@app.get("/api/maps")
def list_maps():
    return ["sample"] + sorted(f.stem for f in (DATA / "demo").glob("*.json"))


@app.get("/api/maps/{map_id}")
def get_map(map_id: str):
    return _load(map_id)


@app.get("/api/maps/{map_id}/path")
def get_path(map_id: str, to: str, from_: str = Query("", alias="from")):
    m = _load(map_id)
    return graph.find_path(m, from_ or m["screens"][0]["id"], to)


@app.post("/api/maps/{map_id}/locate")
def locate(map_id: str, file: UploadFile = File(...)):
    m = _load(map_id)
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "x.png").suffix) as tmp:
        tmp.write(file.file.read())
        tmp.flush()
        try:
            return identify.locate(tmp.name, m)
        except Exception as e:
            raise HTTPException(500, f"locate failed: {type(e).__name__}: {e}")


class ExploreBody(BaseModel):
    url: str
    max_pages: int = 60  # ~1–2.5 s per page measured live
    max_seconds: int = 180


def _run(job_id: str, body: ExploreBody):
    job = JOBS[job_id]
    try:
        out = RUNS_DIR / job_id
        raw = explorer.explore(body.url, str(out), max_pages=body.max_pages, max_seconds=body.max_seconds,
                               on_progress=lambda n, total, _u: job.update(progress=f"{n}/{total} pages"))
        job["progress"] = "building map"
        (out / "map.json").write_text(json.dumps(graph.build_map(raw)))
        job.update(status="done", map_id=job_id, progress="done")
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")


@app.post("/api/explore")
def explore(body: ExploreBody):
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"status": "running", "progress": "exploring"}
    (RUNS_DIR / job_id).mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_run, args=(job_id, body), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return JOBS[job_id]


app.mount("/shots", StaticFiles(directory=DATA), name="shots")
app.mount("/data", StaticFiles(directory=DATA), name="data")
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
